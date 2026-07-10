# 每日股票追蹤 Automation 設定

## 追蹤標的

- **MU** — Micron Technology
- **TSM** — Taiwan Semiconductor
- **SOXX** — iShares Semiconductor ETF

## 執行時間

- **每天晚上 21:30（台灣時間）** — 美股開盤前
- Cron（UTC）：`30 13 * * *`（台灣 UTC+8 的 21:30 = UTC 13:30）

## 在 Cursor 設定 Automation

1. 前往 [cursor.com/automations](https://cursor.com/automations)
2. 點 **New Automation**
3. **Trigger**：Scheduled → Custom cron → `30 13 * * *`
4. **Repository**：`max123465/Label_tool`，分支 `main`
5. **Prompt**（複製以下內容）：

```
你是每日股票追蹤代理。每次執行時：

1. 進入 stock_tracker/ 目錄
2. 執行：pip install -r requirements.txt -q && python stock_tracker/track.py
3. 讀取 stock_tracker/reports/ 最新產生的 daily_*.md 報告
4. 用繁體中文整理成簡潔摘要回覆，包含：
   - MU、TSM、SOXX 現價與漲跌幅
   - 相對前收的變化
   - 若有明顯異動（漲跌 >3%）特別標註
5. 將報告 commit 並 push 到 main（檔名 stock_tracker/reports/daily_YYYY-MM-DD.md）

不要修改 watchlist.json 除非使用者要求變更標的。
```

6. 儲存並啟用

## 手動執行

```bash
pip install -r requirements.txt
python stock_tracker/track.py
```

報告輸出在 `stock_tracker/reports/daily_YYYY-MM-DD.md`。
