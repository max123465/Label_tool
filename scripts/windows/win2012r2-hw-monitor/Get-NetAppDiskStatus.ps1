#Requires -Version 4.0
<#
.SYNOPSIS
  透過 SSH 查 NetApp FAS（如 FAS3220）disk 狀態。只輸出原始結果，不做 Good/Bad 判斷。

.DESCRIPTION
  本機 storcli 看不到 NetApp 內部碟；要 SSH/Telnet 進 controller 查。
  本腳本優先用 plink.exe 或 ssh.exe（Win2012 R2 常見是 PuTTY plink）。

  FAS3220 可能是：
    - 7-Mode  → Mode 7mode
    - Clustered ONTAP → Mode cdot

.PARAMETER Controller
  Controller / cluster management IP 或主機名。雙控請各跑一次，或逗號分隔兩個 IP。

.PARAMETER Username
  登入帳號（常見 admin / root，依你們環境）。

.PARAMETER Password
  密碼（明文參數；內網腳本常用。也可改用 -PasswordEnv）。

.PARAMETER PasswordEnv
  從環境變數讀密碼，例如 NETAPP_PW。

.PARAMETER Mode
  7mode 或 cdot。不確定就先用 auto（兩組指令都試，失敗的會顯示錯誤文字）。

.PARAMETER SshClient
  強制指定：plink / ssh。預設自動找。

.PARAMETER PlinkPath
  plink.exe 完整路徑。

.PARAMETER OutputText
  把輸出存成文字檔。

.EXAMPLE
  .\Get-NetAppDiskStatus.ps1 -Controller 10.1.2.3 -Username admin -Password '***' -Mode 7mode

.EXAMPLE
  $env:NETAPP_PW = '***'
  .\Get-NetAppDiskStatus.ps1 -Controller 10.1.2.3,10.1.2.4 -Username admin -PasswordEnv NETAPP_PW -Mode cdot
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string[]]$Controller,

    [Parameter(Mandatory = $true)]
    [string]$Username,

    [string]$Password = '',
    [string]$PasswordEnv = '',
    [ValidateSet('auto', '7mode', 'cdot')]
    [string]$Mode = 'auto',
    [ValidateSet('', 'plink', 'ssh')]
    [string]$SshClient = '',
    [string]$PlinkPath = '',
    [string]$OutputText = ''
)

$ErrorActionPreference = 'Continue'

# 展開 "a,b" 這種寫法
$targets = @()
foreach ($c in $Controller) {
    foreach ($part in ($c -split ',')) {
        $t = $part.Trim()
        if ($t) { $targets += $t }
    }
}

if ($PasswordEnv) {
    $Password = [Environment]::GetEnvironmentVariable($PasswordEnv)
    if (-not $Password) {
        $Password = [Environment]::GetEnvironmentVariable($PasswordEnv, 'User')
    }
    if (-not $Password) {
        $Password = [Environment]::GetEnvironmentVariable($PasswordEnv, 'Machine')
    }
}
if (-not $Password) {
    Write-Error '需要 -Password 或 -PasswordEnv。'
    exit 1
}

function Find-Plink {
    param([string]$Preferred)
    $cands = @(
        $Preferred,
        'C:\Program Files\PuTTY\plink.exe',
        'C:\Program Files (x86)\PuTTY\plink.exe',
        "$env:USERPROFILE\Desktop\plink.exe",
        'C:\Tools\plink.exe',
        'C:\Scripts\plink.exe'
    )
    $cmd = Get-Command plink.exe -ErrorAction SilentlyContinue
    if ($cmd) { $cands = @($cmd.Source) + $cands }
    foreach ($p in $cands) {
        if ($p -and (Test-Path -LiteralPath $p)) { return (Resolve-Path $p).Path }
    }
    return $null
}

function Resolve-Client {
    if ($SshClient -eq 'plink') {
        $p = Find-Plink -Preferred $PlinkPath
        if (-not $p) { throw '找不到 plink.exe' }
        return @{ Kind = 'plink'; Path = $p }
    }
    if ($SshClient -eq 'ssh') {
        $s = Get-Command ssh.exe -ErrorAction SilentlyContinue
        if (-not $s) { throw '找不到 ssh.exe' }
        return @{ Kind = 'ssh'; Path = $s.Source }
    }
    $p = Find-Plink -Preferred $PlinkPath
    if ($p) { return @{ Kind = 'plink'; Path = $p } }
    $s = Get-Command ssh.exe -ErrorAction SilentlyContinue
    if ($s) { return @{ Kind = 'ssh'; Path = $s.Source } }
    throw '找不到 plink.exe 或 ssh.exe。請安裝 PuTTY plink，或用 -PlinkPath 指定。'
}

function Invoke-NetAppCommand {
    param(
        [hashtable]$Client,
        [string]$HostName,
        [string]$User,
        [string]$Pass,
        [string]$RemoteCommand
    )

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true

    if ($Client.Kind -eq 'plink') {
        $psi.FileName = $Client.Path
        # Quote remote command
        $psi.Arguments = "-ssh -batch -l $User -pw `"$Pass`" $HostName `"$RemoteCommand`""
    } else {
        # ssh.exe 不易安全傳密碼；若你們有 key-based SSH，把 Password 當 unused，改下指令：
        #   ssh user@host "command"
        Write-Warning '使用 ssh.exe 時建議已設定免密金鑰；-Password 不會自動送給 ssh。'
        $psi.FileName = $Client.Path
        $psi.Arguments = "-o BatchMode=yes -o StrictHostKeyChecking=no $User@$HostName `"$RemoteCommand`""
    }

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    [void]$proc.Start()
    $stdout = $proc.StandardOutput.ReadToEnd()
    $stderr = $proc.StandardError.ReadToEnd()
    $proc.WaitForExit(180000) | Out-Null
    return [pscustomobject]@{
        ExitCode = $proc.ExitCode
        Output   = (($stdout + "`n" + $stderr).Trim())
    }
}

$commands7 = @(
    'disk show',
    'aggr status -r',
    'storage show disk'
)

$commandsC = @(
    'storage disk show',
    'storage disk show -broken',
    'storage aggregate show',
    'storage aggregate show-status'
)

if ($Mode -eq '7mode') {
    $commands = $commands7
} elseif ($Mode -eq 'cdot') {
    $commands = $commandsC
} else {
    $commands = $commands7 + $commandsC
}

try {
    $client = Resolve-Client
} catch {
    Write-Error $_.Exception.Message
    exit 1
}

Write-Host ("SSH client : {0}" -f $client.Path)
Write-Host ("Mode       : {0}" -f $Mode)
Write-Host ''

$allText = New-Object System.Text.StringBuilder

foreach ($hostName in $targets) {
    $header = "===== Controller: $hostName ====="
    Write-Host $header -ForegroundColor Cyan
    [void]$allText.AppendLine($header)

    foreach ($cmd in $commands) {
        $title = "--- $cmd ---"
        Write-Host $title
        [void]$allText.AppendLine($title)

        $r = Invoke-NetAppCommand -Client $client -HostName $hostName -User $Username -Pass $Password -RemoteCommand $cmd
        Write-Host $r.Output
        Write-Host ''
        [void]$allText.AppendLine($r.Output)
        [void]$allText.AppendLine('')
    }
}

if ($OutputText) {
    $dir = Split-Path -Parent $OutputText
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    [IO.File]::WriteAllText($OutputText, $allText.ToString(), [Text.Encoding]::UTF8)
    Write-Host ("Saved: {0}" -f $OutputText)
}

Write-Host ''
Write-Host '說明:'
Write-Host '  - 此腳本只查詢，不會 fail disk / 不會改組態。'
Write-Host '  - 若 plink 因 host key 失敗：先手動執行一次 plink user@ip 並接受 fingerprint。'
Write-Host '  - 雙控 FAS3220：-Controller 填兩個 IP，例如 10.1.2.3,10.1.2.4'
Write-Host '  - 不確定 7mode/cdot：用 -Mode auto，看哪組指令有正常表格。'
Write-Host '  - Telnet 不適合自動化；請用 SSH + plink。'
