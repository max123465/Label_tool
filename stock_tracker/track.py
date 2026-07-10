#!/usr/bin/env python3
"""Daily stock tracker for watchlist symbols."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yfinance as yf

WATCHLIST_PATH = Path(__file__).parent / "watchlist.json"
REPORTS_DIR = Path(__file__).parent / "reports"
TZ = ZoneInfo("Asia/Taipei")


def load_watchlist() -> list[str]:
    data = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
    return data["symbols"]


def fmt_price(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"${value:,.2f}"


def fmt_pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def fetch_quote(symbol: str) -> dict:
    ticker = yf.Ticker(symbol)
    info = ticker.info or {}
    hist = ticker.history(period="5d", prepost=True)

    prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
    current = (
        info.get("preMarketPrice")
        or info.get("regularMarketPrice")
        or info.get("currentPrice")
    )

    if current is None and not hist.empty:
        current = float(hist["Close"].iloc[-1])
    if prev_close is None and len(hist) >= 2:
        prev_close = float(hist["Close"].iloc[-2])

    change = None
    change_pct = None
    if current is not None and prev_close:
        change = current - prev_close
        change_pct = (change / prev_close) * 100

    return {
        "symbol": symbol,
        "name": info.get("shortName") or info.get("longName") or symbol,
        "price": current,
        "prev_close": prev_close,
        "change": change,
        "change_pct": change_pct,
        "volume": info.get("volume") or info.get("regularMarketVolume"),
        "market_state": info.get("marketState", "UNKNOWN"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
    }


def build_report(quotes: list[dict], generated_at: datetime) -> str:
    lines = [
        f"# 每日股票追蹤 — {generated_at.strftime('%Y-%m-%d')}",
        "",
        f"> 產生時間：{generated_at.strftime('%Y-%m-%d %H:%M')}（台灣時間）",
        "> 用途：美股開盤前快速掌握 MU / TSM / SOXX 狀況",
        "",
        "| 代號 | 名稱 | 現價 | 前收 | 漲跌 | 漲跌幅 | 成交量 | 52週區間 |",
        "|------|------|------|------|------|--------|--------|----------|",
    ]

    for q in quotes:
        low = q["fifty_two_week_low"]
        high = q["fifty_two_week_high"]
        range_str = (
            f"{fmt_price(low)} – {fmt_price(high)}"
            if low and high
            else "N/A"
        )
        vol = f"{q['volume']:,}" if q["volume"] else "N/A"
        lines.append(
            f"| {q['symbol']} | {q['name']} | {fmt_price(q['price'])} "
            f"| {fmt_price(q['prev_close'])} | {fmt_price(q['change'])} "
            f"| {fmt_pct(q['change_pct'])} | {vol} | {range_str} |"
        )

    lines.extend(
        [
            "",
            "## 個別摘要",
            "",
        ]
    )

    for q in quotes:
        state = q["market_state"]
        state_zh = {
            "PRE": "盤前",
            "REGULAR": "正式盤",
            "POST": "盤後",
            "CLOSED": "休市",
            "PREPRE": "盤前準備",
        }.get(state, state)

        lines.extend(
            [
                f"### {q['symbol']} — {q['name']}",
                "",
                f"- **現價**：{fmt_price(q['price'])}（{state_zh}）",
                f"- **前收**：{fmt_price(q['prev_close'])}",
                f"- **漲跌**：{fmt_price(q['change'])}（{fmt_pct(q['change_pct'])}）",
                f"- **52 週**：{fmt_price(q['fifty_two_week_low'])} – {fmt_price(q['fifty_two_week_high'])}",
                "",
            ]
        )

    return "\n".join(lines)


def main() -> int:
    symbols = load_watchlist()
    now = datetime.now(TZ)
    quotes = []

    print(f"📊 股票追蹤 — {now.strftime('%Y-%m-%d %H:%M')} 台灣時間\n")

    for symbol in symbols:
        try:
            quote = fetch_quote(symbol)
            quotes.append(quote)
            arrow = "▲" if (quote["change_pct"] or 0) >= 0 else "▼"
            print(
                f"{quote['symbol']:5} {fmt_price(quote['price']):>10}  "
                f"{arrow} {fmt_pct(quote['change_pct']):>8}  {quote['name']}"
            )
        except Exception as exc:
            print(f"{symbol:5} ERROR: {exc}", file=sys.stderr)
            quotes.append(
                {
                    "symbol": symbol,
                    "name": symbol,
                    "price": None,
                    "prev_close": None,
                    "change": None,
                    "change_pct": None,
                    "volume": None,
                    "market_state": "ERROR",
                    "fifty_two_week_low": None,
                    "fifty_two_week_high": None,
                }
            )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"daily_{now.strftime('%Y-%m-%d')}.md"
    report_path.write_text(build_report(quotes, now), encoding="utf-8")
    print(f"\n✅ 報告已儲存：{report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
