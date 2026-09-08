#Requires -Version 4.0
<#
.SYNOPSIS
  收集硬體 / RAID / HostMonitor 原始數據（不做好壞判斷）。

.EXAMPLE
  .\Get-HardwareHealth.ps1
  .\Get-HardwareHealth.ps1 -OutputJson .\reports\latest.json
  .\Get-HardwareHealth.ps1 -HostMonitorPath "D:\HostMonitor"
#>
[CmdletBinding()]
param(
    [string]$MegaCliPath = '',
    [string]$IntelRstCliPath = '',
    [string]$HostMonitorPath = '',
    [int]$HostMonitorLogHours = 24,
    [string]$OutputJson = ''
)

$ErrorActionPreference = 'Continue'

function Find-File {
    param([string[]]$Candidates)
    foreach ($p in $Candidates) {
        if ($p -and (Test-Path -LiteralPath $p)) {
            return (Resolve-Path -LiteralPath $p).Path
        }
    }
    return $null
}

function Invoke-Exe {
    param([string]$FilePath, [string[]]$Args)
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    $psi.Arguments = ($Args -join ' ')
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $p = New-Object System.Diagnostics.Process
    $p.StartInfo = $psi
    [void]$p.Start()
    $out = $p.StandardOutput.ReadToEnd()
    $err = $p.StandardError.ReadToEnd()
    $p.WaitForExit(120000) | Out-Null
    return (($out + "`n" + $err).Trim())
}

# --- CPU 平均使用率（抽樣 3 次）---
$cpuSamples = @()
for ($i = 0; $i -lt 3; $i++) {
    $cpu = Get-WmiObject Win32_Processor
    if ($cpu -is [array]) {
        $cpuSamples += [double](($cpu | Measure-Object LoadPercentage -Average).Average)
    } else {
        $cpuSamples += [double]$cpu.LoadPercentage
    }
    if ($i -lt 2) { Start-Sleep -Seconds 1 }
}
$cpuAvg = [math]::Round((($cpuSamples | Measure-Object -Average).Average), 1)

# --- 開機多久 ---
$os = Get-WmiObject Win32_OperatingSystem
$lastBoot = $os.ConvertToDateTime($os.LastBootUpTime)
$uptime = (Get-Date) - $lastBoot

# --- 硬碟容量 ---
$disks = @()
Get-WmiObject Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object {
    if ($_.Size -gt 0) {
        $freePct = [math]::Round(($_.FreeSpace / $_.Size) * 100, 1)
        $disks += [pscustomobject]@{
            Drive       = $_.DeviceID
            SizeGB      = [math]::Round($_.Size / 1GB, 2)
            FreeGB      = [math]::Round($_.FreeSpace / 1GB, 2)
            UsedPercent = [math]::Round(100 - $freePct, 1)
            FreePercent = $freePct
        }
    }
}

# --- LSI MegaRAID（有 CLI 就查；沒有就回 null）---
$megaCandidates = @(
    $MegaCliPath,
    'C:\Program Files\MegaRAID\MegaCli\MegaCli64.exe',
    'C:\Program Files\MegaRAID\MegaCli\MegaCli.exe',
    'C:\Program Files (x86)\MegaRAID\MegaCli\MegaCli64.exe',
    'C:\Program Files\LSI\MegaCLI\MegaCli64.exe',
    'C:\Program Files\MegaRAID\storcli\storcli64.exe',
    'C:\Program Files\Broadcom\storcli\storcli64.exe',
    'C:\MegaCLI\MegaCli64.exe'
)
foreach ($n in @('MegaCli64.exe','MegaCli.exe','storcli64.exe','storcli.exe')) {
    $c = Get-Command $n -ErrorAction SilentlyContinue
    if ($c) { $megaCandidates = @($c.Source) + $megaCandidates }
}
$megaExe = Find-File $megaCandidates
$lsiDrives = @()
$lsiNote = $null
if ($megaExe) {
    if ($megaExe -match '(?i)storcli') {
        $raw = Invoke-Exe $megaExe @('/c0','/eall','/sall','show')
        foreach ($line in ($raw -split "`r?`n")) {
            if ($line -match '(\d+):(\d+)\s+\d+\s+\S+\s+(\S+)') {
                $lsiDrives += [pscustomobject]@{
                    Enclosure = $Matches[1]
                    Slot      = $Matches[2]
                    State     = $Matches[3]
                }
            }
        }
    } else {
        $raw = Invoke-Exe $megaExe @('-PDList','-aALL','-NoLog')
        $cur = $null
        foreach ($line in ($raw -split "`r?`n")) {
            if ($line -match 'Enclosure Device ID:\s*(.+)$') {
                if ($cur) { $lsiDrives += [pscustomobject]$cur }
                $cur = [ordered]@{ Enclosure = $Matches[1].Trim(); Slot = ''; State = ''; Inquiry = '' }
            } elseif ($cur) {
                if ($line -match 'Slot Number:\s*(.+)$') { $cur.Slot = $Matches[1].Trim() }
                elseif ($line -match 'Firmware state:\s*(.+)$') { $cur.State = $Matches[1].Trim() }
                elseif ($line -match 'Inquiry Data:\s*(.+)$') { $cur.Inquiry = $Matches[1].Trim() }
            }
        }
        if ($cur) { $lsiDrives += [pscustomobject]$cur }
    }
} else {
    $lsiNote = 'MegaCLI/StorCLI not found'
}

# --- Intel Rapid RAID（有 rstcli 就查；否則試 WMI）---
$rstCandidates = @(
    $IntelRstCliPath,
    'C:\Program Files\Intel\Intel(R) Rapid Storage Technology Enterprise\CLI\rstcli64.exe',
    'C:\Program Files\Intel\Intel Rapid Storage Technology Enterprise\CLI\rstcli64.exe',
    'C:\Program Files\Intel\RST\rstcli64.exe'
)
foreach ($n in @('rstcli64.exe','rstcli.exe')) {
    $c = Get-Command $n -ErrorAction SilentlyContinue
    if ($c) { $rstCandidates = @($c.Source) + $rstCandidates }
}
$rstExe = Find-File $rstCandidates
$intelInfo = $null
$intelNote = $null
if ($rstExe) {
    $intelInfo = Invoke-Exe $rstExe @('-I','information')
    if (-not $intelInfo) { $intelInfo = Invoke-Exe $rstExe @('-I') }
} else {
    $foundWmi = $false
    foreach ($ns in @('root\IntelRste','root\IntelRaid','root\IntelRST')) {
        try {
            $classes = Get-WmiObject -Namespace $ns -List -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -match '(?i)disk|volume|array' }
            if ($classes) {
                $rows = @()
                foreach ($cls in $classes) {
                    Get-WmiObject -Namespace $ns -Class $cls.Name -ErrorAction SilentlyContinue | ForEach-Object {
                        $rows += ($_ | Select-Object *)
                    }
                }
                $intelInfo = $rows
                $foundWmi = $true
                break
            }
        } catch { }
    }
    if (-not $foundWmi) { $intelNote = 'rstcli / Intel RAID WMI not found' }
}

# --- HostMonitor ---
$hmCandidates = @(
    $HostMonitorPath,
    'C:\Program Files (x86)\HostMonitor',
    'C:\Program Files\HostMonitor',
    'C:\HostMonitor',
    'D:\HostMonitor'
)
$hmPath = Find-File $hmCandidates
if (-not $hmPath) {
    Get-ItemProperty @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
    ) -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -match 'HostMonitor|Host Monitor' } |
        ForEach-Object { if ($_.InstallLocation) { $hmPath = $_.InstallLocation } }
}
$hmService = @(Get-Service -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '(?i)hostmon' -or $_.DisplayName -match '(?i)HostMonitor|Host Monitor' } |
    Select-Object Name, Status, DisplayName)
$hmProcess = @(Get-Process -ErrorAction SilentlyContinue |
    Where-Object { $_.ProcessName -match '(?i)hostmon' } |
    Select-Object ProcessName, Id)

$hmErrors = @()
if ($hmPath) {
    $cutoff = (Get-Date).AddHours(-1 * [math]::Abs($HostMonitorLogHours))
    $dirs = @($hmPath, (Join-Path $hmPath 'Logs'), (Join-Path $hmPath 'Log'))
    $pattern = '(?i)\b(Bad|Down|Alarm|Error|Failed|Failure|Timeout|Unknown|NoAnswer|Critical)\b'
    foreach ($dir in ($dirs | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $dir)) { continue }
        Get-ChildItem -LiteralPath $dir -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Extension -match '(?i)\.(log|txt|csv|htm|html)$' -and $_.LastWriteTime -ge $cutoff } |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 20 |
            ForEach-Object {
                $file = $_.FullName
                try {
                    $lines = Get-Content -LiteralPath $file -ErrorAction Stop
                    if ($lines.Count -gt 2000) { $lines = $lines[($lines.Count - 2000)..($lines.Count - 1)] }
                    foreach ($line in $lines) {
                        if ($line -match $pattern) {
                            $hmErrors += [pscustomobject]@{ File = $file; Line = $line.Trim() }
                        }
                    }
                } catch { }
            }
    }
    $hmErrors = @($hmErrors | Group-Object Line | ForEach-Object { $_.Group[0] } | Select-Object -First 50)
}

# --- 組結果 ---
$result = [pscustomobject]@{
    ComputerName = $env:COMPUTERNAME
    CollectedAt  = (Get-Date).ToString('s')
    CpuUsagePercent = $cpuAvg
    Uptime = [pscustomobject]@{
        LastBootTime = $lastBoot.ToString('s')
        Days         = [math]::Floor($uptime.TotalDays)
        Hours        = $uptime.Hours
        Minutes      = $uptime.Minutes
        Text         = ('{0}d {1}h {2}m' -f [math]::Floor($uptime.TotalDays), $uptime.Hours, $uptime.Minutes)
    }
    Disks = $disks
    LsiMegaRaid = [pscustomobject]@{
        Tool   = $megaExe
        Note   = $lsiNote
        Drives = $lsiDrives
    }
    IntelRapidRaid = [pscustomobject]@{
        Tool = $rstExe
        Note = $intelNote
        Info = $intelInfo
    }
    HostMonitor = [pscustomobject]@{
        Path            = $hmPath
        Services        = $hmService
        Processes       = $hmProcess
        LogHours        = $HostMonitorLogHours
        ErrorLikeLines  = $hmErrors
    }
}

# --- 輸出 ---
Write-Host ("Computer : {0}" -f $result.ComputerName)
Write-Host ("CPU %    : {0}" -f $result.CpuUsagePercent)
Write-Host ("Uptime   : {0} (since {1})" -f $result.Uptime.Text, $result.Uptime.LastBootTime)
Write-Host ''
Write-Host 'Disks:'
$result.Disks | Format-Table -AutoSize | Out-String | Write-Host
Write-Host 'LSI MegaRAID:'
if ($result.LsiMegaRaid.Note) { Write-Host $result.LsiMegaRaid.Note }
elseif ($result.LsiMegaRaid.Drives.Count -eq 0) { Write-Host '(no drives parsed)' }
else { $result.LsiMegaRaid.Drives | Format-Table -AutoSize | Out-String | Write-Host }
Write-Host 'Intel Rapid RAID:'
if ($result.IntelRapidRaid.Note) { Write-Host $result.IntelRapidRaid.Note }
elseif ($result.IntelRapidRaid.Info) { Write-Host ($result.IntelRapidRaid.Info | Out-String) }
else { Write-Host '(no data)' }
Write-Host ''
Write-Host 'HostMonitor:'
Write-Host ("  Path     : {0}" -f $result.HostMonitor.Path)
Write-Host ("  Services : {0}" -f (($result.HostMonitor.Services | ForEach-Object { '{0}={1}' -f $_.Name, $_.Status }) -join '; '))
Write-Host ("  Processes: {0}" -f (($result.HostMonitor.Processes | ForEach-Object ProcessName) -join ', '))
Write-Host ("  Error-like lines (last {0}h): {1}" -f $HostMonitorLogHours, $result.HostMonitor.ErrorLikeLines.Count)
$result.HostMonitor.ErrorLikeLines | Select-Object -First 20 | ForEach-Object {
    Write-Host ("  - {0}" -f $_.Line)
}

if ($OutputJson) {
    $dir = Split-Path -Parent $OutputJson
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputJson -Encoding UTF8
    Write-Host ''
    Write-Host ("JSON: {0}" -f $OutputJson)
}
