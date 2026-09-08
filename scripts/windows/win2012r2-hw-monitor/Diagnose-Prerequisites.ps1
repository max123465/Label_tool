#Requires -Version 4.0
<#
.SYNOPSIS
  台積電 / 內網鎖定環境用：先確認這台 Windows 2012 R2 上「已經有什麼、沒有什麼」。

.DESCRIPTION
  不需要 MegaCLI / StorCLI 也能跑。
  只做盤點，不改系統設定。建議用「系統管理員」開 PowerShell 執行一次。

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\Diagnose-Prerequisites.ps1
#>
[CmdletBinding()]
param(
    [string]$HostMonitorPath = ''
)

$ErrorActionPreference = 'Continue'

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Find-File {
    param([string[]]$Paths)
    foreach ($p in $Paths) {
        if ($p -and (Test-Path -LiteralPath $p)) { return $p }
    }
    return $null
}

Write-Host ''
Write-Host '===== 硬體監控前置檢查 (Diagnose) =====' -ForegroundColor Cyan
Write-Host ("電腦名稱: {0}" -f $env:COMPUTERNAME)
$os = Get-WmiObject Win32_OperatingSystem
$cs = Get-WmiObject Win32_ComputerSystem
Write-Host ("作業系統: {0} ({1})" -f $os.Caption, $os.Version)
Write-Host ("機型: {0} {1}" -f $cs.Manufacturer, $cs.Model)
Write-Host ("系統管理員: {0}" -f $(if (Test-Admin) { '是' } else { '否（建議用系統管理員重跑）' }))

Write-Host ''
Write-Host '--- 1) 有沒有 MegaCLI / StorCLI？ ---' -ForegroundColor Yellow
$megaCandidates = @(
    'C:\Program Files\MegaRAID\MegaCli\MegaCli64.exe',
    'C:\Program Files\MegaRAID\MegaCli\MegaCli.exe',
    'C:\Program Files (x86)\MegaRAID\MegaCli\MegaCli64.exe',
    'C:\Program Files\LSI\MegaCLI\MegaCli64.exe',
    'C:\Program Files\MegaRAID\storcli\storcli64.exe',
    'C:\Program Files\Broadcom\storcli\storcli64.exe',
    'C:\MegaCLI\MegaCli64.exe',
    'C:\storcli\storcli64.exe'
)
foreach ($n in @('MegaCli64.exe','MegaCli.exe','storcli64.exe','storcli.exe')) {
    $c = Get-Command $n -ErrorAction SilentlyContinue
    if ($c) { $megaCandidates = @($c.Source) + $megaCandidates }
}
$mega = Find-File $megaCandidates
if ($mega) {
    Write-Host ("[有] {0}" -f $mega) -ForegroundColor Green
    Write-Host '    → 可以精確查出哪一個 Enclosure:Slot 壞掉'
} else {
    Write-Host '[沒有] 找不到 MegaCli64 / storcli64' -ForegroundColor DarkYellow
    Write-Host '    → 沒關係，主腳本會改用「Windows 事件紀錄」判斷 LSI RAID 異常'
    Write-Host '    → 但可能無法顯示精確槽位；若要槽位需請 IT 提供 MegaCLI（可免安裝、只放 exe）'
}

Write-Host ''
Write-Host '--- 2) 有沒有 Intel rstcli？ ---' -ForegroundColor Yellow
$rstCandidates = @(
    'C:\Program Files\Intel\Intel(R) Rapid Storage Technology Enterprise\CLI\rstcli64.exe',
    'C:\Program Files\Intel\Intel Rapid Storage Technology Enterprise\CLI\rstcli64.exe',
    'C:\Program Files\Intel\Intel Rapid Storage Technology\rstcli64.exe',
    'C:\Program Files\Intel\RST\rstcli64.exe'
)
foreach ($n in @('rstcli64.exe','rstcli.exe')) {
    $c = Get-Command $n -ErrorAction SilentlyContinue
    if ($c) { $rstCandidates = @($c.Source) + $rstCandidates }
}
$rst = Find-File $rstCandidates
$intelWmi = $false
foreach ($ns in @('root\IntelRste','root\IntelRaid','root\IntelRST')) {
    try {
        $list = Get-WmiObject -Namespace $ns -List -ErrorAction SilentlyContinue
        if ($list) { $intelWmi = $true; Write-Host ("[有] Intel RAID WMI: {0}" -f $ns) -ForegroundColor Green; break }
    } catch { }
}
if ($rst) {
    Write-Host ("[有] {0}" -f $rst) -ForegroundColor Green
} elseif (-not $intelWmi) {
    Write-Host '[沒有] rstcli / Intel RAID WMI' -ForegroundColor DarkYellow
    Write-Host '    → 主腳本會改用事件紀錄判斷 Intel RAID'
} else {
    Write-Host '[部分] 沒有 rstcli，但有 Intel RAID WMI（可用）' -ForegroundColor Green
}

Write-Host ''
Write-Host '--- 3) Windows 看得到哪些 RAID/儲存控制器？ ---' -ForegroundColor Yellow
$ctrls = @()
try {
    $ctrls += @(Get-WmiObject Win32_SCSIController -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name)
    $ctrls += @(Get-WmiObject Win32_IDEController -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name)
} catch { }
$ctrls = @($ctrls | Where-Object { $_ -match '(?i)LSI|MegaRAID|Intel|RAID|SAS|SATA|Storage' } | Select-Object -Unique)
if ($ctrls.Count -eq 0) {
    Write-Host '（沒有明顯的 RAID 控制器名稱；仍可能有驅動以其他名稱存在）'
} else {
    $ctrls | ForEach-Object { Write-Host ("  - {0}" -f $_) }
}

Write-Host ''
Write-Host '--- 4) HostMonitor 9.x ---' -ForegroundColor Yellow
$hmCandidates = @(
    $HostMonitorPath,
    'C:\Program Files (x86)\HostMonitor',
    'C:\Program Files\HostMonitor',
    'C:\HostMonitor',
    'D:\HostMonitor'
)
$hm = Find-File $hmCandidates
if (-not $hm) {
    Get-ItemProperty 'HKLM:\SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
                     'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -match 'HostMonitor|Host Monitor' } |
        ForEach-Object {
            if ($_.InstallLocation) { $hm = $_.InstallLocation }
            Write-Host ("[登錄檔] {0} {1}" -f $_.DisplayName, $_.DisplayVersion)
        }
}
$svc = Get-Service -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -match 'HostMonitor|Host Monitor' -or $_.Name -match 'hostmon' }
$proc = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '(?i)hostmon' }
if ($hm) { Write-Host ("[有] 安裝路徑: {0}" -f $hm) -ForegroundColor Green }
else { Write-Host '[找不到路徑] 若你確定有裝，請用 -HostMonitorPath 指定' -ForegroundColor DarkYellow }
if ($svc) { $svc | ForEach-Object { Write-Host ("[服務] {0} = {1}" -f $_.DisplayName, $_.Status) } }
else { Write-Host '[服務] 未找到名稱含 HostMonitor 的服務' }
if ($proc) { Write-Host ("[行程] 正在執行: {0}" -f (($proc | ForEach-Object ProcessName) -join ', ')) -ForegroundColor Green }
else { Write-Host '[行程] 目前沒看到 HostMonitor process' }

Write-Host ''
Write-Host '--- 5) 建議你這樣跑（一次成功） ---' -ForegroundColor Cyan
Write-Host '用「系統管理員」開啟 CMD 或 PowerShell，到腳本目錄後執行：'
Write-Host ''
Write-Host '  powershell -ExecutionPolicy Bypass -File .\Diagnose-Prerequisites.ps1' -ForegroundColor White
Write-Host '  powershell -ExecutionPolicy Bypass -File .\Get-HardwareHealth.ps1 -OutputJson .\reports\latest.json' -ForegroundColor White
Write-Host ''
Write-Host '重點：'
Write-Host '  1. 沒有 MegaCLI / storcli / rstcli 也可以跑，不會整支掛掉。'
Write-Host '  2. CPU / 開機時間 / 磁碟容量 / Windows 磁碟健康 / 事件紀錄 / HostMonitor 都會查。'
Write-Host '  3. 沒有 MegaCLI 時，LSI「哪一槽壞掉」可能只能從事件文字猜；精確槽位要請 IT 給 MegaCli64.exe。'
Write-Host '  4. 若 HostMonitor 不在預設路徑：'
Write-Host '     .\Get-HardwareHealth.ps1 -HostMonitorPath "D:\你的路徑\HostMonitor" -OutputJson .\reports\latest.json'
Write-Host ''
Write-Host '===== 檢查結束 =====' -ForegroundColor Cyan
