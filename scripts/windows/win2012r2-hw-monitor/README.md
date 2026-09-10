# 硬體 / NetApp 數據收集（只輸出數據，不做好壞判斷）

## 檔案

| 檔案 | 做什麼 |
|---|---|
| `Get-HardwareHealth.ps1` | 本機 CPU / uptime / 磁碟% / LSI / Intel / HostMonitor |
| `Get-NetAppDiskStatus.ps1` | SSH 進 NetApp FAS（如 FAS3220）查 disk 狀態 |
| `Diagnose-Prerequisites.ps1` | 可選：先看本機有沒有 MegaCLI / HostMonitor |
| `Run-HardwareHealth.cmd` | 一鍵跑本機主程式 |
| `paths.example.ini` | 路徑備註，可忽略 |

## 本機硬體

```bat
powershell -ExecutionPolicy Bypass -File .\Get-HardwareHealth.ps1 -OutputJson .\reports\latest.json
```

## NetApp FAS3220 disks（用 SSH，不是 storcli）

先準備 `plink.exe`（PuTTY）。第一次請手動連一次接受 host key：

```bat
plink.exe admin@10.1.2.3
```

然後：

```bat
powershell -ExecutionPolicy Bypass -File .\Get-NetAppDiskStatus.ps1 -Controller 10.1.2.3 -Username admin -Password "***" -Mode 7mode
```

雙控：

```bat
powershell -ExecutionPolicy Bypass -File .\Get-NetAppDiskStatus.ps1 -Controller 10.1.2.3,10.1.2.4 -Username admin -Password "***" -Mode auto -OutputText .\reports\netapp-disks.txt
```

- `-Mode 7mode`：舊 7-Mode（`disk show` / `aggr status -r`）
- `-Mode cdot`：Clustered ONTAP（`storage disk show` 等）
- `-Mode auto`：兩組都跑，看哪邊有正常表格

只讀查詢，不會改 NetApp 組態。Telnet 不適合自動化，請用 SSH + plink。
