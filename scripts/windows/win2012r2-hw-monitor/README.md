# 硬體數據收集（只輸出數據，不做好壞判斷）

## 檔案

| 檔案 | 做什麼 |
|---|---|
| `Get-HardwareHealth.ps1` | 主程式：收集並顯示數據 |
| `Diagnose-Prerequisites.ps1` | 可選：先看有沒有 MegaCLI / HostMonitor |
| `Run-HardwareHealth.cmd` | 一鍵跑主程式，結果存 `reports\` |
| `paths.example.ini` | 路徑備註，可忽略 |

## 用法

```bat
powershell -ExecutionPolicy Bypass -File .\Get-HardwareHealth.ps1
powershell -ExecutionPolicy Bypass -File .\Get-HardwareHealth.ps1 -OutputJson .\reports\latest.json
```

HostMonitor 不在預設路徑時：

```bat
powershell -ExecutionPolicy Bypass -File .\Get-HardwareHealth.ps1 -HostMonitorPath "D:\HostMonitor" -OutputJson .\reports\latest.json
```

## 會輸出什麼

- `CpuUsagePercent`：CPU 平均使用率（抽樣 3 次）
- `Uptime`：開機多久
- `Disks`：各槽容量、已用%、剩餘%
- `LsiMegaRaid.Drives`：有 MegaCLI/StorCLI 才有；否則 Note 說明找不到
- `IntelRapidRaid.Info`：有 rstcli/WMI 才有
- `HostMonitor.ErrorLikeLines`：近 N 小時 log 裡含 Bad/Error/Down 等字樣的行

**不做 OK/WARN/BAD 判斷，數據給你自己看。**

只讀查詢，不重開機、不改 RAID、不停服務。唯一寫入是可選的 JSON 報告檔。
