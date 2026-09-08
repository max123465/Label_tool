# Windows Server 2012 R2 — Hardware / RAID / HostMonitor health script

## 台積電 / 內網鎖定環境（推薦一次成功流程）

**不確定有沒有 MegaCLI / StorCLI / rstcli？沒關係，先跑 Diagnose。**

1. 把整個 `win2012r2-hw-monitor` 資料夾拷到 server（例如 `C:\Scripts\hw-monitor\`）
2. **右鍵 → 以系統管理員身分** 開 CMD
3. 執行：

```bat
cd /d C:\Scripts\hw-monitor
Run-HardwareHealth.cmd
```

或分兩步：

```bat
powershell -ExecutionPolicy Bypass -File .\Diagnose-Prerequisites.ps1
powershell -ExecutionPolicy Bypass -File .\Get-HardwareHealth.ps1 -OutputJson .\reports\latest.json
```

### 沒有 MegaCLI 時會怎樣？

| 項目 | 沒有 MegaCLI / storcli / rstcli |
|---|---|
| CPU / 開機時間 / 磁碟容量% | 正常（Windows 內建） |
| Windows 磁碟健康 | 正常（WMI / Get-PhysicalDisk） |
| LSI 哪顆壞 | **改掃事件紀錄**（常能知道有壞碟；精確槽位可能沒有） |
| Intel Rapid RAID | 改用 WMI 或事件紀錄 |
| HostMonitor error | 照常掃 log / 服務 / 行程 |

Hardware MegaRAID 在 Windows 裡通常只顯示「一顆虛擬碟」，**沒有原廠 CLI 時無法 100% 保證列出 E:S 槽位**。  
若 Diagnose 顯示沒有 MegaCLI、但你一定要槽位，請 IT 提供可攜的 `MegaCli64.exe`（不一定要正式安裝）。

## Important limitation (this Cloud Agent)

Cursor Cloud Agent 是 Linux，無法在雲端建 Windows 2012 R2。請在實際 server 上執行本資料夾腳本。

## What the script collects

| Section | Source | Notes |
|---|---|---|
| Preflight | 路徑探測 | 告訴你有沒有 CLI / HostMonitor / 控制器 |
| CPU usage % | `Win32_Processor` | WARN ≥75%, BAD ≥90% |
| Uptime | `Win32_OperatingSystem` | |
| Disk capacity % | `Win32_LogicalDisk` | WARN free ≤15%, BAD free ≤5% |
| WindowsDiskHealth | WMI / Storage | 不需 MegaCLI |
| LsiMegaRaid | MegaCLI **或** Event Log | 沒 CLI 也能跑 |
| IntelRapidRaid | rstcli / WMI / Event Log | 沒 CLI 也能跑 |
| RaidEventLog | System/Application | 72 小時 RAID/Disk 事件 |
| HostMonitor | logs + service | HostMonitor 9.x |

Exit codes: `0` = OK, `1` = WARN, `2` = BAD/ERROR.

## Optional parameters

```powershell
.\Get-HardwareHealth.ps1 `
  -MegaCliPath "C:\Tools\MegaCli64.exe" `
  -IntelRstCliPath "C:\Tools\rstcli64.exe" `
  -HostMonitorPath "D:\HostMonitor" `
  -HostMonitorLogHours 48 `
  -OutputJson .\reports\latest.json
```

## Task Scheduler

1. 動作：`C:\Scripts\hw-monitor\Run-HardwareHealth.cmd`
2. 最高權限執行
3. 設定為 Windows Server 2012 R2
