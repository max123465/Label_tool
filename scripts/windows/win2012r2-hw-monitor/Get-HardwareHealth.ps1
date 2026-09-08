#Requires -Version 4.0
<#
.SYNOPSIS
  Collect hardware / RAID / HostMonitor health info on Windows Server 2012 R2.

.DESCRIPTION
  Gathers:
    - Preflight inventory (do you have MegaCLI/rstcli/HostMonitor?)
    - CPU usage (%)
    - System uptime
    - Logical disk free/used percentage
    - Windows disk health (no vendor CLI required)
    - LSI MegaRAID unhealthy drives (MegaCLI/StorCLI OR Event Log fallback)
    - Intel Rapid RAID / RSTe (rstcli / WMI / Event Log fallback)
    - RAID-related Windows Event Log scan
    - HostMonitor 9.x recent Bad/Error/Down/Unknown entries from logs

  Designed for locked-down Windows Server 2012 R2 (PowerShell 4.0).
  Missing MegaCLI does NOT abort the script. Run elevated for best results.

.PARAMETER MegaCliPath
  Optional full path to MegaCli64.exe / MegaCli.exe / storcli64.exe.

.PARAMETER IntelRstCliPath
  Optional full path to rstcli64.exe / rstcli.exe.

.PARAMETER HostMonitorPath
  Optional HostMonitor install folder. Auto-detected when omitted.

.PARAMETER HostMonitorLogHours
  How many hours of HostMonitor log lines to scan. Default: 24.

.PARAMETER OutputJson
  Also write a JSON report to this path.

.PARAMETER Quiet
  Suppress console pretty print; still returns objects / writes JSON.

.EXAMPLE
  .\Get-HardwareHealth.ps1

.EXAMPLE
  .\Get-HardwareHealth.ps1 -OutputJson C:\Temp\hw-health.json -HostMonitorLogHours 48
#>
[CmdletBinding()]
param(
    [string]$MegaCliPath = '',
    [string]$IntelRstCliPath = '',
    [string]$HostMonitorPath = '',
    [int]$HostMonitorLogHours = 24,
    [string]$OutputJson = '',
    [switch]$Quiet
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

function New-SectionResult {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Status,
        [object]$Data = $null,
        [string]$Message = ''
    )
    [pscustomobject]@{
        Name      = $Name
        Status    = $Status   # OK | WARN | BAD | SKIP | ERROR
        Message   = $Message
        Data      = $Data
        CheckedAt = (Get-Date).ToString('s')
    }
}

function Write-Section {
    param([pscustomobject]$Section)
    if ($Quiet) { return }
    $color = switch ($Section.Status) {
        'OK'    { 'Green' }
        'WARN'  { 'Yellow' }
        'BAD'   { 'Red' }
        'SKIP'  { 'DarkGray' }
        'ERROR' { 'Magenta' }
        default { 'White' }
    }
    Write-Host ''
    Write-Host ("=== {0} [{1}] ===" -f $Section.Name, $Section.Status) -ForegroundColor $color
    if ($Section.Message) {
        Write-Host $Section.Message
    }
    if ($null -ne $Section.Data) {
        $Section.Data | Format-List | Out-String | Write-Host
    }
}

function Test-IsAdministrator {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($id)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Find-FirstExistingFile {
    param([string[]]$Candidates)
    foreach ($p in $Candidates) {
        if ($p -and (Test-Path -LiteralPath $p)) {
            return (Resolve-Path -LiteralPath $p).Path
        }
    }
    return $null
}

function Invoke-ExternalText {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList
    )
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    $psi.Arguments = ($ArgumentList -join ' ')
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $p = New-Object System.Diagnostics.Process
    $p.StartInfo = $psi
    [void]$p.Start()
    $stdout = $p.StandardOutput.ReadToEnd()
    $stderr = $p.StandardError.ReadToEnd()
    $p.WaitForExit(120000) | Out-Null
    [pscustomobject]@{
        ExitCode = $p.ExitCode
        StdOut   = $stdout
        StdErr   = $stderr
        Combined = (($stdout + "`n" + $stderr).Trim())
    }
}

# ---------------------------------------------------------------------------
# CPU
# ---------------------------------------------------------------------------
function Get-CpuUsageInfo {
    try {
        $samples = @()
        for ($i = 0; $i -lt 3; $i++) {
            $c = Get-WmiObject -Class Win32_Processor -ErrorAction Stop
            if ($c -is [array]) {
                $avg = ($c | Measure-Object -Property LoadPercentage -Average).Average
            } else {
                $avg = [double]$c.LoadPercentage
            }
            $samples += [double]$avg
            if ($i -lt 2) { Start-Sleep -Seconds 1 }
        }
        $cpu = [math]::Round((($samples | Measure-Object -Average).Average), 1)
        $status = 'OK'
        if ($cpu -ge 90) { $status = 'BAD' }
        elseif ($cpu -ge 75) { $status = 'WARN' }

        $data = [pscustomobject]@{
            CpuUsagePercent = $cpu
            SampleCount     = $samples.Count
            Samples         = ($samples -join ', ')
            LogicalProcessors = (Get-WmiObject -Class Win32_ComputerSystem).NumberOfLogicalProcessors
        }
        return (New-SectionResult -Name 'CPU' -Status $status -Data $data -Message ("CPU usage: {0}%" -f $cpu))
    } catch {
        return (New-SectionResult -Name 'CPU' -Status 'ERROR' -Message $_.Exception.Message)
    }
}

# ---------------------------------------------------------------------------
# Uptime
# ---------------------------------------------------------------------------
function Get-UptimeInfo {
    try {
        $os = Get-WmiObject -Class Win32_OperatingSystem -ErrorAction Stop
        $lastBoot = $os.ConvertToDateTime($os.LastBootUpTime)
        $uptime = (Get-Date) - $lastBoot
        $data = [pscustomobject]@{
            LastBootTime = $lastBoot.ToString('s')
            UptimeDays   = [math]::Floor($uptime.TotalDays)
            UptimeHours  = $uptime.Hours
            UptimeMinutes = $uptime.Minutes
            UptimeText   = ('{0}d {1}h {2}m' -f [math]::Floor($uptime.TotalDays), $uptime.Hours, $uptime.Minutes)
            TotalSeconds = [math]::Round($uptime.TotalSeconds, 0)
        }
        return (New-SectionResult -Name 'Uptime' -Status 'OK' -Data $data -Message ("Uptime: {0} (since {1})" -f $data.UptimeText, $data.LastBootTime))
    } catch {
        return (New-SectionResult -Name 'Uptime' -Status 'ERROR' -Message $_.Exception.Message)
    }
}

# ---------------------------------------------------------------------------
# Disk capacity
# ---------------------------------------------------------------------------
function Get-DiskCapacityInfo {
    try {
        $disks = Get-WmiObject -Class Win32_LogicalDisk -Filter "DriveType=3" -ErrorAction Stop
        $rows = @()
        $worst = 'OK'
        foreach ($d in $disks) {
            if ($d.Size -le 0) { continue }
            $freePct = [math]::Round(($d.FreeSpace / $d.Size) * 100, 1)
            $usedPct = [math]::Round(100 - $freePct, 1)
            $st = 'OK'
            if ($freePct -le 5) { $st = 'BAD' }
            elseif ($freePct -le 15) { $st = 'WARN' }
            if ($st -eq 'BAD') { $worst = 'BAD' }
            elseif ($st -eq 'WARN' -and $worst -eq 'OK') { $worst = 'WARN' }

            $rows += [pscustomobject]@{
                Drive          = $d.DeviceID
                VolumeName     = $d.VolumeName
                SizeGB         = [math]::Round($d.Size / 1GB, 2)
                FreeGB         = [math]::Round($d.FreeSpace / 1GB, 2)
                UsedPercent    = $usedPct
                FreePercent    = $freePct
                Status         = $st
            }
        }
        $msg = ($rows | ForEach-Object { '{0} used {1}% (free {2}%)' -f $_.Drive, $_.UsedPercent, $_.FreePercent }) -join '; '
        return (New-SectionResult -Name 'DiskCapacity' -Status $worst -Data $rows -Message $msg)
    } catch {
        return (New-SectionResult -Name 'DiskCapacity' -Status 'ERROR' -Message $_.Exception.Message)
    }
}

# ---------------------------------------------------------------------------
# LSI MegaRAID / StorCLI
# ---------------------------------------------------------------------------
function Resolve-MegaCliPath {
    param([string]$Preferred)
    if ($Preferred) {
        $found = Find-FirstExistingFile -Candidates @($Preferred)
        if ($found) { return $found }
    }
    $candidates = @(
        'C:\Program Files\MegaRAID\MegaCli\MegaCli64.exe',
        'C:\Program Files\MegaRAID\MegaCli\MegaCli.exe',
        'C:\Program Files (x86)\MegaRAID\MegaCli\MegaCli64.exe',
        'C:\Program Files (x86)\MegaRAID\MegaCli\MegaCli.exe',
        'C:\Program Files\LSI\MegaCLI\MegaCli64.exe',
        'C:\Program Files\LSI\MegaCLI\MegaCli.exe',
        'C:\Program Files\MegaRAID\storcli\storcli64.exe',
        'C:\Program Files\MegaRAID\storcli\storcli.exe',
        'C:\Program Files\Broadcom\storcli\storcli64.exe',
        'C:\Program Files\Broadcom\storcli\storcli.exe',
        'C:\MegaCLI\MegaCli64.exe',
        'C:\storcli\storcli64.exe'
    )
    # Also search PATH
    foreach ($name in @('MegaCli64.exe', 'MegaCli.exe', 'storcli64.exe', 'storcli.exe')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { $candidates = @($cmd.Source) + $candidates }
    }
    return (Find-FirstExistingFile -Candidates $candidates)
}

function Parse-MegaCliPdList {
    param([string]$Text)
    $drives = @()
    $cur = $null
    foreach ($line in ($Text -split "`r?`n")) {
        if ($line -match '^\s*Enclosure Device ID:\s*(.+)\s*$') {
            if ($cur) { $drives += $cur }
            $cur = [ordered]@{
                Enclosure = $Matches[1].Trim()
                Slot = ''
                DeviceId = ''
                State = ''
                MediaError = ''
                OtherError = ''
                PredictiveFailure = ''
                Inquiry = ''
                RawSize = ''
            }
        } elseif ($null -ne $cur) {
            if ($line -match '^\s*Slot Number:\s*(.+)\s*$') { $cur.Slot = $Matches[1].Trim() }
            elseif ($line -match '^\s*Device Id:\s*(.+)\s*$') { $cur.DeviceId = $Matches[1].Trim() }
            elseif ($line -match '^\s*Firmware state:\s*(.+)\s*$') { $cur.State = $Matches[1].Trim() }
            elseif ($line -match '^\s*Media Error Count:\s*(.+)\s*$') { $cur.MediaError = $Matches[1].Trim() }
            elseif ($line -match '^\s*Other Error Count:\s*(.+)\s*$') { $cur.OtherError = $Matches[1].Trim() }
            elseif ($line -match '^\s*Predictive Failure Count:\s*(.+)\s*$') { $cur.PredictiveFailure = $Matches[1].Trim() }
            elseif ($line -match '^\s*Inquiry Data:\s*(.+)\s*$') { $cur.Inquiry = $Matches[1].Trim() }
            elseif ($line -match '^\s*Raw Size:\s*(.+)\s*$') { $cur.RawSize = $Matches[1].Trim() }
        }
    }
    if ($cur) { $drives += $cur }
    return @($drives | ForEach-Object { [pscustomobject]$_ })
}

function Parse-StorCliJsonDrives {
    param([object]$Json)
    $rows = @()
    try {
        foreach ($ctrl in @($Json.Controllers)) {
            $resp = $ctrl.'Response Data'
            if (-not $resp) { continue }
            # Prefer detailed PD list if present
            $pdKeys = @($resp.PSObject.Properties.Name | Where-Object { $_ -like 'Drive /c*/e*/s*' })
            if ($pdKeys.Count -gt 0) {
                foreach ($k in $pdKeys) {
                    $pd = $resp.$k
                    if (-not $pd) { continue }
                    $state = ''
                    if ($pd.'State') { $state = [string]$pd.'State' }
                    elseif ($pd.PSObject.Properties['Drive Information']) {
                        $state = [string]$pd.'Drive Information'.State
                    }
                    $rows += [pscustomobject]@{
                        Enclosure = $k
                        Slot = ''
                        DeviceId = ''
                        State = $state
                        MediaError = ''
                        OtherError = ''
                        PredictiveFailure = ''
                        Inquiry = ''
                        RawSize = ''
                        Source = 'storcli-json-detail'
                    }
                }
            }
            if ($resp.'PD LIST') {
                foreach ($pd in @($resp.'PD LIST')) {
                    $rows += [pscustomobject]@{
                        Enclosure = [string]$pd.EID
                        Slot = [string]$pd.Slt
                        DeviceId = [string]$pd.DID
                        State = [string]$pd.State
                        MediaError = ''
                        OtherError = ''
                        PredictiveFailure = ''
                        Inquiry = [string]$pd.Model
                        RawSize = [string]$pd.Size
                        Source = 'storcli-json-pdlist'
                    }
                }
            }
        }
    } catch {
        # fall through
    }
    return $rows
}

function Test-RaidDriveUnhealthy {
    param([string]$State)
    if (-not $State) { return $true }
    $s = $State.ToLowerInvariant()
    # Explicit bad patterns first (StorCLI uses UBad for Unconfigured-Bad)
    if ($s -match 'fail|offline|missing|unconfigured\(bad\)|ubad|rebuild|degraded|error') {
        return $true
    }
    $healthy = @(
        'online', 'online, spun up', 'onln', 'hotspare', 'hotspr', 'ghs', 'dhs',
        'ready', 'ugood', 'unconfigured(good)', 'unconfigured good',
        'copyback', 'jbod'
    )
    foreach ($h in $healthy) {
        if ($s -eq $h -or $s.StartsWith($h)) { return $false }
    }
    # Online* is ok
    if ($s -match '^online') { return $false }
    if ($s -match '^onln') { return $false }
    return $true
}

function Get-RaidRelatedEvents {
    param(
        [int]$Hours = 72,
        [string]$VendorFilter = ''  # '', 'lsi', 'intel'
    )
    $cutoff = (Get-Date).AddHours(-1 * [math]::Abs($Hours))
    $sourcePattern = '(?i)MR_MONITOR|MegaRAID|megasas|LSI|storelib|MSM|Intel.?RAID|iaStor|RstMw|IRST|Rapid Storage|Disk|disk'
    if ($VendorFilter -eq 'lsi') {
        $sourcePattern = '(?i)MR_MONITOR|MegaRAID|megasas|LSI|storelib|MSM|SAS'
    } elseif ($VendorFilter -eq 'intel') {
        $sourcePattern = '(?i)Intel.?RAID|iaStor|RstMw|IRST|Rapid Storage|iaStorA'
    }
    $msgPattern = '(?i)(fail|failed|failure|degraded|rebuild|offline|predictive|hot spare|missing|error|bad|unconfigured|PD |physical drive|slot)'
    $hits = @()

    # Prefer Get-WinEvent; fall back to Get-EventLog on older/locked systems
    foreach ($logName in @('System', 'Application')) {
        try {
            $ev = Get-WinEvent -FilterHashtable @{ LogName = $logName; StartTime = $cutoff } -ErrorAction SilentlyContinue |
                Where-Object {
                    ($_.ProviderName -match $sourcePattern -or $_.Message -match '(?i)MegaRAID|LSI|Intel Rapid|RAID') -and
                    ($_.Level -le 3 -or $_.Message -match $msgPattern)
                } |
                Select-Object -First 80
            foreach ($e in @($ev)) {
                $msg = ''
                if ($e.Message) {
                    $one = ($e.Message -replace '\s+', ' ').Trim()
                    $msg = $one.Substring(0, [Math]::Min(350, $one.Length))
                }
                if ($VendorFilter -eq 'lsi' -and $msg -notmatch '(?i)MegaRAID|LSI|megasas|MR_|SAS|PD |physical' -and $e.ProviderName -notmatch '(?i)MegaRAID|LSI|megasas|MR_') {
                    continue
                }
                if ($VendorFilter -eq 'intel' -and $msg -notmatch '(?i)Intel|iaStor|RST|Rapid' -and $e.ProviderName -notmatch '(?i)Intel|iaStor|RST') {
                    continue
                }
                $hits += [pscustomobject]@{
                    Time     = $e.TimeCreated.ToString('s')
                    Log      = $logName
                    Source   = $e.ProviderName
                    Level    = $e.LevelDisplayName
                    EventId  = $e.Id
                    Message  = $msg
                }
            }
        } catch {
            try {
                $legacy = Get-EventLog -LogName $logName -After $cutoff -ErrorAction SilentlyContinue |
                    Where-Object {
                        $_.Source -match $sourcePattern -and
                        ($_.EntryType -match 'Error|Warning' -or $_.Message -match $msgPattern)
                    } |
                    Select-Object -First 80
                foreach ($e in @($legacy)) {
                    $one = ($e.Message -replace '\s+', ' ').Trim()
                    $hits += [pscustomobject]@{
                        Time     = $e.TimeGenerated.ToString('s')
                        Log      = $logName
                        Source   = $e.Source
                        Level    = [string]$e.EntryType
                        EventId  = $e.EventID
                        Message  = $one.Substring(0, [Math]::Min(350, $one.Length))
                    }
                }
            } catch { }
        }
    }

    return @($hits | Sort-Object Time -Descending | Select-Object -First 100)
}

function Get-WindowsDiskHealthInfo {
    # Always-available path: no MegaCLI required.
    $rows = @()
    $problems = @()

    try {
        $drives = Get-WmiObject Win32_DiskDrive -ErrorAction Stop
        foreach ($d in @($drives)) {
            $st = [string]$d.Status
            $pred = $null
            try { $pred = $d.PredictFailure } catch { }
            $row = [pscustomobject]@{
                Model          = $d.Model
                InterfaceType  = $d.InterfaceType
                MediaType      = $d.MediaType
                SizeGB         = if ($d.Size) { [math]::Round($d.Size / 1GB, 2) } else { 0 }
                Status         = $st
                PredictFailure = $pred
                SerialNumber   = $d.SerialNumber
                DeviceID       = $d.DeviceID
                Source         = 'Win32_DiskDrive'
            }
            $rows += $row
            if ($st -and $st -notmatch '(?i)^OK$|^Online$') {
                $problems += ("{0} Status={1}" -f $d.Model, $st)
            }
            if ($pred -eq $true) {
                $problems += ("{0} PredictFailure=True" -f $d.Model)
            }
        }
    } catch {
        return (New-SectionResult -Name 'WindowsDiskHealth' -Status 'ERROR' -Message $_.Exception.Message)
    }

    # Storage module (present on most 2012 R2)
    try {
        Import-Module Storage -ErrorAction SilentlyContinue
        $pds = Get-PhysicalDisk -ErrorAction SilentlyContinue
        foreach ($p in @($pds)) {
            $rows += [pscustomobject]@{
                Model          = $p.FriendlyName
                InterfaceType  = [string]$p.BusType
                MediaType      = [string]$p.MediaType
                SizeGB         = if ($p.Size) { [math]::Round($p.Size / 1GB, 2) } else { 0 }
                Status         = ('{0}/{1}' -f $p.HealthStatus, $p.OperationalStatus)
                PredictFailure = $null
                SerialNumber   = $p.SerialNumber
                DeviceID       = [string]$p.DeviceId
                Source         = 'Get-PhysicalDisk'
            }
            if ([string]$p.HealthStatus -and [string]$p.HealthStatus -ne 'Healthy') {
                $problems += ("PhysicalDisk {0} Health={1} Op={2}" -f $p.FriendlyName, $p.HealthStatus, $p.OperationalStatus)
            }
        }
    } catch { }

    # Controllers visible to Windows
    $controllers = @()
    try {
        $controllers = @(Get-WmiObject Win32_SCSIController -ErrorAction SilentlyContinue |
            Select-Object Name, DriverName, Status)
    } catch { }

    $data = [pscustomobject]@{
        Disks = $rows
        Controllers = $controllers
        Problems = $problems
        Note = 'Hardware MegaRAID usually appears as ONE virtual disk to Windows; slot-level failure needs MegaCLI or Event Log.'
    }

    if ($problems.Count -gt 0) {
        return (New-SectionResult -Name 'WindowsDiskHealth' -Status 'BAD' -Data $data -Message ($problems -join '; '))
    }
    return (New-SectionResult -Name 'WindowsDiskHealth' -Status 'OK' -Data $data -Message ("Windows sees {0} disk(s); Status OK/Healthy." -f $rows.Count))
}

function Get-RaidEventLogInfo {
    param([int]$Hours = 72)
    $hits = Get-RaidRelatedEvents -Hours $Hours -VendorFilter ''
    # Keep likely actionable ones
    $badish = @($hits | Where-Object {
        $_.Level -match '(?i)Error|Warning|Critical' -or
        $_.Message -match '(?i)fail|degraded|rebuild|offline|predictive|missing|unconfigured\(bad\)|hot.?spare'
    })
    $data = [pscustomobject]@{
        HoursScanned = $Hours
        EventCount = $hits.Count
        ActionableCount = $badish.Count
        Events = $badish
        Method = 'Windows Event Log (no MegaCLI required)'
    }
    if ($badish.Count -gt 0) {
        $msg = ("RAID/Disk related warning/error events in last {0}h: {1}" -f $Hours, $badish.Count)
        return (New-SectionResult -Name 'RaidEventLog' -Status 'BAD' -Data $data -Message $msg)
    }
    return (New-SectionResult -Name 'RaidEventLog' -Status 'OK' -Data $data -Message ("No RAID/Disk warning/error events in last {0}h." -f $Hours))
}

function Get-EnvironmentPreflight {
    param(
        [string]$MegaCliPath,
        [string]$IntelRstCliPath,
        [string]$HostMonitorPath
    )
    $mega = Resolve-MegaCliPath -Preferred $MegaCliPath
    $rst = Resolve-IntelRstCliPath -Preferred $IntelRstCliPath
    $hm = Resolve-HostMonitorPath -Preferred $HostMonitorPath

    $controllers = @()
    try {
        $controllers = @(Get-WmiObject Win32_SCSIController -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '(?i)LSI|MegaRAID|Intel|RAID|SAS|SATA' } |
            Select-Object -ExpandProperty Name -Unique)
    } catch { }
    try {
        Get-WmiObject Win32_IDEController -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '(?i)Intel|RAID|RST' } |
            ForEach-Object { $controllers += $_.Name }
    } catch { }
    $controllers = @($controllers | Select-Object -Unique)

    $hasLsiCtrl = ($controllers | Where-Object { $_ -match '(?i)LSI|MegaRAID|SAS' }).Count -gt 0
    $hasIntelCtrl = ($controllers | Where-Object { $_ -match '(?i)Intel|RST' }).Count -gt 0

    $advice = @()
    if (-not $mega -and $hasLsiCtrl) {
        $advice += 'Detected LSI/MegaRAID-looking controller but NO MegaCLI/StorCLI. Will use Event Log + Windows disk health. Slot number (E:S) needs MegaCLI if IT can provide it.'
    }
    if (-not $mega -and -not $hasLsiCtrl) {
        $advice += 'No MegaCLI/StorCLI and no obvious LSI controller name in WMI. LSI section may SKIP; Event Log still scanned.'
    }
    if (-not $rst -and $hasIntelCtrl) {
        $advice += 'Detected Intel RAID-looking controller but NO rstcli. Will try Intel WMI + Event Log.'
    }
    if (-not $hm) {
        $advice += 'HostMonitor path not auto-found. Pass -HostMonitorPath if installed elsewhere.'
    } else {
        $advice += ('HostMonitor found at: {0}' -f $hm)
    }
    if ($mega) { $advice += ('RAID CLI found: {0}' -f $mega) }
    if ($rst) { $advice += ('Intel RST CLI found: {0}' -f $rst) }

    $data = [pscustomobject]@{
        IsAdmin          = Test-IsAdministrator
        MegaCliOrStorCli = $mega
        IntelRstCli      = $rst
        HostMonitorPath  = $hm
        Controllers      = $controllers
        Advice           = $advice
    }

    $status = 'OK'
    if (-not (Test-IsAdministrator)) {
        $status = 'WARN'
        $advice = @('Not Administrator — some RAID/event queries may be incomplete.') + $advice
        $data.Advice = $advice
    }

    return (New-SectionResult -Name 'Preflight' -Status $status -Data $data -Message ($advice -join ' | '))
}

function Get-LsiMegaRaidInfo {
    param(
        [string]$PreferredPath,
        [int]$EventHours = 72
    )
    $exe = Resolve-MegaCliPath -Preferred $PreferredPath

    # Path A: MegaCLI / StorCLI present — best, can name the bad slot
    if ($exe) {
        $isStorCli = ($exe -match '(?i)storcli')
        try {
            $drives = @()
            $raw = ''
            if ($isStorCli) {
                $r = Invoke-ExternalText -FilePath $exe -ArgumentList @('/c0', '/eall', '/sall', 'show', 'J')
                $raw = $r.Combined
                if ($r.StdOut) {
                    try {
                        $json = $r.StdOut | ConvertFrom-Json
                        $drives = @(Parse-StorCliJsonDrives -Json $json)
                    } catch { }
                }
                if ($drives.Count -eq 0) {
                    $r2 = Invoke-ExternalText -FilePath $exe -ArgumentList @('/c0', '/eall', '/sall', 'show')
                    $raw = $r2.Combined
                    foreach ($line in ($raw -split "`r?`n")) {
                        if ($line -match '(\d+):(\d+)\s+\d+\s+\S+\s+(\S+)') {
                            $drives += [pscustomobject]@{
                                Enclosure = $Matches[1]
                                Slot = $Matches[2]
                                DeviceId = ''
                                State = $Matches[3]
                                MediaError = ''
                                OtherError = ''
                                PredictiveFailure = ''
                                Inquiry = ''
                                RawSize = ''
                                Source = 'storcli-text'
                            }
                        }
                    }
                }
            } else {
                $r = Invoke-ExternalText -FilePath $exe -ArgumentList @('-PDList', '-aALL', '-NoLog')
                $raw = $r.Combined
                $drives = @(Parse-MegaCliPdList -Text $raw)
            }

            if ($drives.Count -eq 0) {
                return (New-SectionResult -Name 'LsiMegaRaid' -Status 'WARN' -Data ([pscustomobject]@{ Tool = $exe; RawSnippet = ($raw.Substring(0, [Math]::Min(500, $raw.Length))) }) -Message 'CLI found but no physical drives parsed. Check controller / permissions.')
            }

            $bad = @()
            foreach ($d in $drives) {
                $unhealthy = Test-RaidDriveUnhealthy -State ([string]$d.State)
                $pred = 0
                [void][int]::TryParse([string]$d.PredictiveFailure, [ref]$pred)
                if ($unhealthy -or $pred -gt 0) {
                    $bad += [pscustomobject]@{
                        Location = ('E{0}:S{1}' -f $d.Enclosure, $d.Slot)
                        Enclosure = $d.Enclosure
                        Slot = $d.Slot
                        DeviceId = $d.DeviceId
                        State = $d.State
                        PredictiveFailure = $d.PredictiveFailure
                        MediaError = $d.MediaError
                        Inquiry = $d.Inquiry
                    }
                }
            }

            $data = [pscustomobject]@{
                Method = 'MegaCLI/StorCLI'
                Tool = $exe
                DriveCount = $drives.Count
                Drives = $drives
                FailedOrUnhealthy = $bad
            }

            if ($bad.Count -gt 0) {
                $msg = 'Unhealthy drive(s): ' + (($bad | ForEach-Object { '{0} state={1}' -f $_.Location, $_.State }) -join '; ')
                return (New-SectionResult -Name 'LsiMegaRaid' -Status 'BAD' -Data $data -Message $msg)
            }
            return (New-SectionResult -Name 'LsiMegaRaid' -Status 'OK' -Data $data -Message ("All {0} physical drive(s) look healthy." -f $drives.Count))
        } catch {
            return (New-SectionResult -Name 'LsiMegaRaid' -Status 'ERROR' -Message $_.Exception.Message)
        }
    }

    # Path B: no CLI (common in locked-down sites) — Event Log fallback
    $events = Get-RaidRelatedEvents -Hours $EventHours -VendorFilter 'lsi'
    $actionable = @($events | Where-Object {
        $_.Level -match '(?i)Error|Warning|Critical' -or
        $_.Message -match '(?i)fail|degraded|rebuild|offline|predictive|missing|PD |physical drive|slot'
    })

    $data = [pscustomobject]@{
        Method = 'EventLogFallback'
        Tool = $null
        Note = 'MegaCLI/StorCLI not installed. Cannot resolve exact enclosure:slot without CLI. Scanning LSI/MegaRAID-related Windows events instead.'
        EventHours = $EventHours
        Events = $actionable
    }

    if ($actionable.Count -gt 0) {
        # Try extract slot hints from messages
        $slotHints = @()
        foreach ($e in $actionable) {
            if ($e.Message -match '(?i)slot\s*#?\s*(\d+)' -or $e.Message -match '(?i)PD\s*[:=]?\s*(\d+)' -or $e.Message -match '(\d+)\s*:\s*(\d+)') {
                $slotHints += $e.Message
            }
        }
        $msg = ("No MegaCLI; found {0} LSI/MegaRAID-related warning/error event(s) in last {1}h." -f $actionable.Count, $EventHours)
        if ($slotHints.Count -gt 0) {
            $msg += ' Possible slot hints in event text.'
            $data.SlotHints = $slotHints
        }
        return (New-SectionResult -Name 'LsiMegaRaid' -Status 'BAD' -Data $data -Message $msg)
    }

    return (New-SectionResult -Name 'LsiMegaRaid' -Status 'OK' -Data $data -Message ("No MegaCLI/StorCLI found; no LSI/MegaRAID warning/error events in last {0}h (fallback OK)." -f $EventHours))
}

# ---------------------------------------------------------------------------
# Intel Rapid RAID / RSTe
# ---------------------------------------------------------------------------
function Resolve-IntelRstCliPath {
    param([string]$Preferred)
    if ($Preferred) {
        $found = Find-FirstExistingFile -Candidates @($Preferred)
        if ($found) { return $found }
    }
    $candidates = @(
        'C:\Program Files\Intel\Intel(R) Rapid Storage Technology Enterprise\CLI\rstcli64.exe',
        'C:\Program Files\Intel\Intel(R) Rapid Storage Technology Enterprise\CLI\rstcli.exe',
        'C:\Program Files\Intel\Intel Rapid Storage Technology Enterprise\CLI\rstcli64.exe',
        'C:\Program Files\Intel\Intel Rapid Storage Technology\rstcli64.exe',
        'C:\Program Files (x86)\Intel\Intel(R) Rapid Storage Technology Enterprise\CLI\rstcli64.exe',
        'C:\Program Files\Intel\RST\rstcli64.exe'
    )
    foreach ($name in @('rstcli64.exe', 'rstcli.exe')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { $candidates = @($cmd.Source) + $candidates }
    }
    return (Find-FirstExistingFile -Candidates $candidates)
}

function Get-IntelRapidRaidInfo {
    param([string]$PreferredPath)
    $exe = Resolve-IntelRstCliPath -Preferred $PreferredPath
    $info = [ordered]@{ Tool = $exe; Method = ''; Volumes = @(); Disks = @(); Problems = @() }

    # Method 1: rstcli
    if ($exe) {
        try {
            $r = Invoke-ExternalText -FilePath $exe -ArgumentList @('-I', 'information')
            if (-not $r.Combined) {
                $r = Invoke-ExternalText -FilePath $exe -ArgumentList @('--information')
            }
            if (-not $r.Combined) {
                $r = Invoke-ExternalText -FilePath $exe -ArgumentList @('-I')
            }
            $info.Method = 'rstcli'
            $info.Raw = $r.Combined
            $text = $r.Combined
            $problems = @()
            foreach ($line in ($text -split "`r?`n")) {
                if ($line -match '(?i)(degraded|failed|missing|offline|error|rebuild)') {
                    $problems += $line.Trim()
                }
            }
            # Try to capture disk status lines
            $disks = @()
            foreach ($line in ($text -split "`r?`n")) {
                if ($line -match '(?i)Disk\s+(\d+).*(?:State|Status)\s*[:=]\s*(.+)$' -or
                    $line -match '(?i)^\s*-\s*(.+?)\s*:\s*(Normal|Failed|Degraded|Missing|Offline).*$') {
                    $disks += $line.Trim()
                }
            }
            $info.Disks = $disks
            $info.Problems = $problems
            if ($problems.Count -gt 0) {
                return (New-SectionResult -Name 'IntelRapidRaid' -Status 'BAD' -Data ([pscustomobject]$info) -Message ($problems -join '; '))
            }
            if ($text -match '(?i)no\s+controller|not\s+found|error') {
                # continue to WMI fallback
            } else {
                return (New-SectionResult -Name 'IntelRapidRaid' -Status 'OK' -Data ([pscustomobject]$info) -Message 'rstcli reported no degraded/failed disk lines.')
            }
        } catch {
            $info.CliError = $_.Exception.Message
        }
    }

    # Method 2: WMI namespaces used by Intel RST/RSTe
    $nsList = @('root\IntelRste', 'root\IntelRaid', 'root\IntelRST', 'root\raid')
    foreach ($ns in $nsList) {
        try {
            $vols = Get-WmiObject -Namespace $ns -Class 'Intel_OromRaidVolume' -ErrorAction SilentlyContinue
            if (-not $vols) {
                $vols = Get-WmiObject -Namespace $ns -List -ErrorAction SilentlyContinue |
                    Where-Object { $_.Name -match 'Volume|Disk|Array' }
            }
            $diskClasses = Get-WmiObject -Namespace $ns -List -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -match '(?i)disk|device|pd|member' }
            if ($vols -or $diskClasses) {
                $info.Method = "WMI:$ns"
                $problems = @()
                $diskRows = @()
                foreach ($cls in @($diskClasses)) {
                    try {
                        $objs = Get-WmiObject -Namespace $ns -Class $cls.Name -ErrorAction SilentlyContinue
                        foreach ($o in @($objs)) {
                            $stateProp = $o.PSObject.Properties | Where-Object { $_.Name -match '(?i)state|status|health' } | Select-Object -First 1
                            $nameProp = $o.PSObject.Properties | Where-Object { $_.Name -match '(?i)name|model|device|serial' } | Select-Object -First 1
                            $stateVal = if ($stateProp) { [string]$stateProp.Value } else { '' }
                            $nameVal = if ($nameProp) { [string]$nameProp.Value } else { $cls.Name }
                            $diskRows += [pscustomobject]@{ Class = $cls.Name; Name = $nameVal; State = $stateVal }
                            if ($stateVal -and $stateVal -match '(?i)fail|degrad|missing|offline|error|bad') {
                                $problems += ("{0}={1}" -f $nameVal, $stateVal)
                            }
                        }
                    } catch { }
                }
                $info.Disks = $diskRows
                $info.Problems = $problems
                if ($problems.Count -gt 0) {
                    return (New-SectionResult -Name 'IntelRapidRaid' -Status 'BAD' -Data ([pscustomobject]$info) -Message ($problems -join '; '))
                }
                return (New-SectionResult -Name 'IntelRapidRaid' -Status 'OK' -Data ([pscustomobject]$info) -Message ("Intel RAID WMI namespace {0} reachable; no failed state detected." -f $ns))
            }
        } catch { }
    }

    if (-not $exe) {
        # Path C: Event Log only
        $events = Get-RaidRelatedEvents -Hours 72 -VendorFilter 'intel'
        $actionable = @($events | Where-Object {
            $_.Level -match '(?i)Error|Warning|Critical' -or
            $_.Message -match '(?i)fail|degraded|rebuild|offline|missing'
        })
        $info.Method = 'EventLogFallback'
        $info.Problems = @($actionable | ForEach-Object { $_.Message })
        $info.Events = $actionable
        if ($actionable.Count -gt 0) {
            return (New-SectionResult -Name 'IntelRapidRaid' -Status 'BAD' -Data ([pscustomobject]$info) -Message ("No rstcli/WMI; found {0} Intel RAID-related warning/error event(s)." -f $actionable.Count))
        }
        return (New-SectionResult -Name 'IntelRapidRaid' -Status 'OK' -Data ([pscustomobject]$info) -Message 'No rstcli/Intel RAID WMI; no Intel RAID warning/error events in last 72h (fallback OK).')
    }
    return (New-SectionResult -Name 'IntelRapidRaid' -Status 'WARN' -Data ([pscustomobject]$info) -Message 'Intel RST CLI present but could not confirm volume health via CLI/WMI.')
}

# ---------------------------------------------------------------------------
# HostMonitor 9.x
# ---------------------------------------------------------------------------
function Resolve-HostMonitorPath {
    param([string]$Preferred)
    if ($Preferred -and (Test-Path -LiteralPath $Preferred)) {
        return (Resolve-Path -LiteralPath $Preferred).Path
    }
    $candidates = @(
        'C:\Program Files (x86)\HostMonitor',
        'C:\Program Files\HostMonitor',
        'C:\HostMonitor',
        'D:\HostMonitor'
    )
    # Uninstall registry
    $regPaths = @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )
    foreach ($rp in $regPaths) {
        try {
            Get-ItemProperty $rp -ErrorAction SilentlyContinue |
                Where-Object { $_.DisplayName -match 'HostMonitor|Host Monitor' } |
                ForEach-Object {
                    if ($_.InstallLocation) { $candidates = @($_.InstallLocation) + $candidates }
                }
        } catch { }
    }
    foreach ($c in $candidates) {
        if ($c -and (Test-Path -LiteralPath $c)) { return (Resolve-Path -LiteralPath $c).Path }
    }
    return $null
}

function Get-HostMonitorInfo {
    param(
        [string]$PreferredPath,
        [int]$Hours
    )
    $root = Resolve-HostMonitorPath -Preferred $PreferredPath
    $svc = Get-Service -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '(?i)hostmon|HostMonitor' -or $_.DisplayName -match '(?i)HostMonitor|Host Monitor' }
    $proc = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '(?i)hostmon|hm$' }

    if (-not $root -and -not $svc -and -not $proc) {
        return (New-SectionResult -Name 'HostMonitor' -Status 'SKIP' -Message 'HostMonitor install path / service / process not found. Pass -HostMonitorPath if installed elsewhere.')
    }

    $cutoff = (Get-Date).AddHours(-1 * [math]::Abs($Hours))
    $errorHits = @()
    $logFilesScanned = @()

    $logDirs = @()
    if ($root) {
        $logDirs += $root
        $logDirs += (Join-Path $root 'Logs')
        $logDirs += (Join-Path $root 'Log')
        $logDirs += (Join-Path $root 'logs')
    }
    # Common alternate log folders
    $logDirs += 'C:\Program Files (x86)\HostMonitor\Logs'
    $logDirs += 'C:\HostMonitor\Logs'

    $patterns = '(?i)\b(Bad|Down|Alarm|Error|Failed|Failure|Timeout|Unknown|NoAnswer|No Answer|Critical)\b'

    foreach ($dir in ($logDirs | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $dir)) { continue }
        $files = Get-ChildItem -LiteralPath $dir -File -ErrorAction SilentlyContinue |
            Where-Object {
                $_.Extension -match '(?i)\.(log|txt|csv|htm|html)$' -and
                $_.LastWriteTime -ge $cutoff
            } |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 30

        foreach ($f in $files) {
            $logFilesScanned += $f.FullName
            try {
                # Read tail-ish: last ~4000 lines for large logs
                $lines = Get-Content -LiteralPath $f.FullName -ErrorAction Stop
                if ($lines.Count -gt 4000) {
                    $lines = $lines[($lines.Count - 4000)..($lines.Count - 1)]
                }
                foreach ($line in $lines) {
                    if ($line -match $patterns -and $line -notmatch '(?i)scriptres:ok') {
                        # Prefer recent dated lines when parseable; otherwise keep
                        $include = $true
                        if ($line -match '(\d{1,4}[/-]\d{1,2}[/-]\d{1,4}\s+\d{1,2}:\d{2}(:\d{2})?)') {
                            try {
                                $dt = [datetime]::Parse($Matches[1], [Globalization.CultureInfo]::InvariantCulture)
                                if ($dt -lt $cutoff) { $include = $false }
                            } catch { }
                        }
                        if ($include) {
                            $errorHits += [pscustomobject]@{
                                File = $f.FullName
                                Line = $line.Trim()
                            }
                        }
                    }
                }
            } catch { }
        }
    }

    # Also scan Application event log for HostMonitor source (if present)
    try {
        $events = Get-WinEvent -FilterHashtable @{ LogName = 'Application'; StartTime = $cutoff } -ErrorAction SilentlyContinue |
            Where-Object { $_.ProviderName -match '(?i)HostMonitor|HostMon|KS-Soft' -and $_.Level -le 3 } |
            Select-Object -First 50
        foreach ($e in @($events)) {
            $errorHits += [pscustomobject]@{
                File = ('EventLog:{0}' -f $e.ProviderName)
                Line = ('[{0}] {1}' -f $e.TimeCreated.ToString('s'), ($e.Message -replace '\s+', ' ').Substring(0, [Math]::Min(300, ($e.Message -replace '\s+', ' ').Length)))
            }
        }
    } catch {
        # Get-WinEvent may be limited; try legacy
        try {
            $legacy = Get-EventLog -LogName Application -After $cutoff -ErrorAction SilentlyContinue |
                Where-Object { $_.Source -match '(?i)HostMonitor|HostMon' -and $_.EntryType -match 'Error|Warning' } |
                Select-Object -First 50
            foreach ($e in @($legacy)) {
                $errorHits += [pscustomobject]@{
                    File = ('EventLog:{0}' -f $e.Source)
                    Line = ('[{0}] {1}' -f $e.TimeGenerated.ToString('s'), ($e.Message -replace '\s+', ' ').Substring(0, [Math]::Min(300, ($e.Message -replace '\s+', ' ').Length)))
                }
            }
        } catch { }
    }

    # Deduplicate
    $unique = @($errorHits | Group-Object -Property Line | ForEach-Object { $_.Group[0] } | Select-Object -First 100)

    $svcInfo = @($svc | Select-Object Name, Status, StartType, DisplayName)
    $procInfo = @($proc | Select-Object ProcessName, Id, StartTime)
    $data = [pscustomobject]@{
        InstallPath       = $root
        Services          = $svcInfo
        Processes         = $procInfo
        LogHours          = $Hours
        LogFilesScanned   = $logFilesScanned
        ErrorEntries      = $unique
        ErrorCount        = $unique.Count
    }

    $svcBad = $false
    foreach ($s in @($svc)) {
        if ($s.Status -ne 'Running') { $svcBad = $true }
    }

    if ($unique.Count -gt 0) {
        $msg = ("HostMonitor issues in last {0}h: {1} unique error-like line(s)." -f $Hours, $unique.Count)
        return (New-SectionResult -Name 'HostMonitor' -Status 'BAD' -Data $data -Message $msg)
    }
    if ($svcBad) {
        return (New-SectionResult -Name 'HostMonitor' -Status 'WARN' -Data $data -Message 'HostMonitor service exists but is not Running; no recent error log lines matched.')
    }
    if ($root -and $logFilesScanned.Count -eq 0) {
        return (New-SectionResult -Name 'HostMonitor' -Status 'WARN' -Data $data -Message 'HostMonitor found, but no recent log files matched. Confirm log folder / logging is enabled in HostMonitor Options.')
    }
    return (New-SectionResult -Name 'HostMonitor' -Status 'OK' -Data $data -Message ("No Bad/Error/Down-like HostMonitor log entries in last {0}h." -f $Hours))
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
$started = Get-Date
if (-not (Test-IsAdministrator)) {
    Write-Warning 'Not running as Administrator. RAID CLI tools often require elevation.'
}

$cs = Get-WmiObject Win32_ComputerSystem
$os = Get-WmiObject Win32_OperatingSystem
$header = [pscustomobject]@{
    ComputerName = $env:COMPUTERNAME
    Manufacturer = $cs.Manufacturer
    Model        = $cs.Model
    OS           = $os.Caption
    OSVersion    = $os.Version
    CollectedAt  = $started.ToString('s')
}

if (-not $Quiet) {
    Write-Host ("Hardware Health Report - {0}" -f $header.ComputerName) -ForegroundColor Cyan
    Write-Host ("{0} | {1} {2}" -f $header.OS, $header.Manufacturer, $header.Model)
}

$sections = @()
$sections += Get-EnvironmentPreflight -MegaCliPath $MegaCliPath -IntelRstCliPath $IntelRstCliPath -HostMonitorPath $HostMonitorPath
$sections += Get-CpuUsageInfo
$sections += Get-UptimeInfo
$sections += Get-DiskCapacityInfo
$sections += Get-WindowsDiskHealthInfo
$sections += Get-LsiMegaRaidInfo -PreferredPath $MegaCliPath -EventHours 72
$sections += Get-IntelRapidRaidInfo -PreferredPath $IntelRstCliPath
$sections += Get-RaidEventLogInfo -Hours 72
$sections += Get-HostMonitorInfo -PreferredPath $HostMonitorPath -Hours $HostMonitorLogHours

foreach ($s in $sections) { Write-Section -Section $s }

# Overall: Preflight WARN alone should not fail the run; BAD/ERROR elsewhere does.
$overall = 'OK'
foreach ($s in $sections) {
    if ($s.Name -eq 'Preflight') { continue }
    if ($s.Status -eq 'BAD' -or $s.Status -eq 'ERROR') { $overall = 'BAD'; break }
    elseif ($s.Status -eq 'WARN' -and $overall -eq 'OK') { $overall = 'WARN' }
}
# If only Preflight is WARN and everything else OK, surface WARN so operator notices non-admin / missing tools advice
$pre = $sections | Where-Object { $_.Name -eq 'Preflight' } | Select-Object -First 1
if ($overall -eq 'OK' -and $pre -and $pre.Status -eq 'WARN') {
    $overall = 'WARN'
}

$report = [pscustomobject]@{
    Overall  = $overall
    Header   = $header
    Sections = $sections
}

if ($OutputJson) {
    $dir = Split-Path -Parent $OutputJson
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputJson -Encoding UTF8
    if (-not $Quiet) {
        Write-Host ''
        Write-Host ("JSON written: {0}" -f $OutputJson) -ForegroundColor Cyan
    }
}

if (-not $Quiet) {
    Write-Host ''
    $oc = switch ($overall) { 'OK' { 'Green' } 'WARN' { 'Yellow' } default { 'Red' } }
    Write-Host ("OVERALL: {0}" -f $overall) -ForegroundColor $oc
}

# Exit codes for monitoring systems / Task Scheduler
# 0 = OK, 1 = WARN, 2 = BAD/ERROR
switch ($overall) {
    'OK'   { exit 0 }
    'WARN' { exit 1 }
    default { exit 2 }
}
