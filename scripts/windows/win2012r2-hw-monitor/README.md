# Windows Server 2012 R2 — Hardware / RAID / HostMonitor health script

## Important limitation (this Cloud Agent)

This Cursor Cloud Agent runs on **Linux**. It **cannot** install or boot a real Windows Server 2012 R2 guest here (no Hyper-V/Windows ISO provisioning in this environment).

What this folder provides instead:

1. A ready-to-run PowerShell 4.0 script for your **existing** Win2012 R2 host
2. A CMD wrapper for Task Scheduler
3. Copy / install checklist for MegaCLI, Intel RST CLI, and HostMonitor 9.90

Deploy the files under `scripts/windows/win2012r2-hw-monitor/` onto the Windows server (for example `C:\Scripts\hw-monitor\`).

## What the script collects

| Section | Source | Notes |
|---|---|---|
| CPU usage % | `Win32_Processor.LoadPercentage` (3 samples) | WARN ≥75%, BAD ≥90% |
| Uptime | `Win32_OperatingSystem.LastBootUpTime` | Days / hours / minutes |
| Disk capacity % | `Win32_LogicalDisk` (fixed drives) | WARN free ≤15%, BAD free ≤5% |
| LSI MegaRAID bad disks | `MegaCli64.exe` or `storcli64.exe` | Parses PD list / firmware state |
| Intel Rapid RAID | `rstcli64.exe` or Intel RAID WMI | Looks for Failed/Degraded/Missing |
| HostMonitor errors | HostMonitor logs + Application event log | Scans last N hours for Bad/Down/Error |

Exit codes: `0` = OK, `1` = WARN, `2` = BAD/ERROR.

## Prerequisites on the Windows server

1. **PowerShell 4.0+** (built into Server 2012 R2)
2. Run **as Administrator** (RAID CLIs usually need elevation)
3. Tools (install if missing):

### LSI MegaRAID
- Install **MegaCLI** (`MegaCli64.exe`) or **StorCLI** (`storcli64.exe`)
- Common paths the script auto-searches:
  - `C:\Program Files\MegaRAID\MegaCli\MegaCli64.exe`
  - `C:\Program Files\MegaRAID\storcli\storcli64.exe`
  - `C:\Program Files\Broadcom\storcli\storcli64.exe`
- Or pass: `-MegaCliPath "D:\Tools\MegaCli64.exe"`

### Intel Rapid RAID / RSTe
- Install Intel Rapid Storage Technology Enterprise CLI (`rstcli64.exe`)
- Or ensure Intel RAID WMI namespace exists (`root\IntelRste` / `root\IntelRaid`)
- Or pass: `-IntelRstCliPath "C:\Path\rstcli64.exe"`

### HostMonitor 9.90
- Keep HostMonitor logging enabled (Options → Log)
- Default folders searched:
  - `C:\Program Files (x86)\HostMonitor`
  - `C:\Program Files\HostMonitor`
  - `...\Logs`
- Or pass: `-HostMonitorPath "D:\HostMonitor"`
- Tip: text/HTML/CSV common logs work best for this parser

## Usage

```powershell
cd C:\Scripts\hw-monitor

# Interactive
.\Get-HardwareHealth.ps1

# JSON report
.\Get-HardwareHealth.ps1 -OutputJson C:\Scripts\hw-monitor\reports\latest.json

# Custom tool paths / longer HostMonitor window
.\Get-HardwareHealth.ps1 `
  -MegaCliPath "C:\MegaCLI\MegaCli64.exe" `
  -IntelRstCliPath "C:\Program Files\Intel\RST\rstcli64.exe" `
  -HostMonitorPath "C:\Program Files (x86)\HostMonitor" `
  -HostMonitorLogHours 48 `
  -OutputJson C:\Scripts\hw-monitor\reports\latest.json
```

Or double-click / schedule:

```bat
Run-HardwareHealth.cmd
```

## Task Scheduler (recommended)

1. Create Basic Task → trigger every 5–15 minutes (or hourly)
2. Action: start `C:\Scripts\hw-monitor\Run-HardwareHealth.cmd`
3. Run whether user is logged on or not
4. Run with highest privileges
5. Configure for **Windows Server 2012 R2**
6. Optional: alert when last exit code is `2`

## Execution policy

If scripts are blocked:

```powershell
Set-ExecutionPolicy RemoteSigned -Scope LocalMachine
```

Or always launch via the `.cmd` wrapper (`-ExecutionPolicy Bypass`).

## Interpreting RAID “bad disk” output

For LSI, unhealthy examples of `Firmware state`:

- `Offline`
- `Failed`
- `Unconfigured(bad)`
- `Rebuild` (WARN/BAD depending on policy — treated as unhealthy here)
- Predictive Failure Count &gt; 0

Location is shown as `E&lt;enclosure&gt;:S&lt;slot&gt;` so you can map to the physical bay.

## HostMonitor note

HostMonitor stores alerts in the log type you configured (Text / HTML / DBF / ODBC). This script scrapes recent text-like logs and Application event log entries. If you only use ODBC logging, either:

- also enable a text common log, or
- extend the script to query your ODBC DSN

## Manual smoke test checklist on the real server

1. `powershell -File Get-HardwareHealth.ps1` as Admin
2. Confirm CPU / Uptime / Disk sections are OK
3. Confirm LSI section is OK or SKIP (not ERROR)
4. Confirm Intel section is OK or SKIP
5. Confirm HostMonitor section finds install path and scans logs
6. Optionally fail a test test in HostMonitor and re-run with `-HostMonitorLogHours 1`
