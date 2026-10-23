from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime

from . import config
from .classify import DEFAULT_CATEGORIES

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    date TEXT,
    merchant TEXT,
    seller_tax_id TEXT,
    invoice_no TEXT,
    amount REAL,
    category TEXT,
    note TEXT DEFAULT '',
    items TEXT DEFAULT '[]',
    image TEXT,
    thumb TEXT,
    source TEXT,
    status TEXT NOT NULL,
    message TEXT DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_invoice_no ON expenses(invoice_no) WHERE invoice_no IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_date ON expenses(date);
CREATE TABLE IF NOT EXISTS categories (
    name TEXT PRIMARY KEY,
    sort INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS merchant_rules (
    key TEXT PRIMARY KEY,
    merchant TEXT,
    category TEXT
);
"""

FIELDS = ["date", "merchant", "seller_tax_id", "invoice_no", "amount", "category", "note",
          "items", "image", "thumb", "source", "status", "message"]


def conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.executescript(SCHEMA)
        if not _conn.execute("SELECT 1 FROM categories LIMIT 1").fetchone():
            _conn.executemany("INSERT INTO categories(name, sort) VALUES (?, ?)",
                              [(c, i) for i, c in enumerate(DEFAULT_CATEGORIES)])
        _conn.commit()
    return _conn


def _row(r: sqlite3.Row | None) -> dict | None:
    if r is None:
        return None
    d = dict(r)
    d["items"] = json.loads(d.get("items") or "[]")
    return d


def categories() -> list[str]:
    with _lock:
        return [r["name"] for r in conn().execute("SELECT name FROM categories ORDER BY sort, name")]


def add_category(name: str) -> None:
    with _lock:
        c = conn()
        sort = c.execute("SELECT COALESCE(MAX(sort), 0) + 1 FROM categories").fetchone()[0]
        c.execute("INSERT OR IGNORE INTO categories(name, sort) VALUES (?, ?)", (name, sort))
        c.commit()


def delete_category(name: str) -> None:
    with _lock:
        c = conn()
        c.execute("DELETE FROM categories WHERE name = ?", (name,))
        c.execute("UPDATE expenses SET category = '其他' WHERE category = ?", (name,))
        c.execute("DELETE FROM merchant_rules WHERE category = ?", (name,))
        if not c.execute("SELECT 1 FROM categories WHERE name = '其他'").fetchone():
            c.execute("INSERT INTO categories(name, sort) VALUES ('其他', 999)")
        c.commit()


def create_expense(**values) -> int:
    values.setdefault("status", "done")
    values["created_at"] = datetime.now().isoformat(timespec="seconds")
    if isinstance(values.get("items"), list):
        values["items"] = json.dumps(values["items"], ensure_ascii=False)
    cols = ["created_at"] + [k for k in FIELDS if k in values]
    with _lock:
        c = conn()
        cur = c.execute(
            f"INSERT INTO expenses({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
            [values[k] for k in cols],
        )
        c.commit()
        return cur.lastrowid


def update_expense(expense_id: int, **values) -> None:
    values = {k: v for k, v in values.items() if k in FIELDS}
    if not values:
        return
    if isinstance(values.get("items"), list):
        values["items"] = json.dumps(values["items"], ensure_ascii=False)
    with _lock:
        c = conn()
        c.execute(
            f"UPDATE expenses SET {', '.join(f'{k} = ?' for k in values)} WHERE id = ?",
            [*values.values(), expense_id],
        )
        c.commit()


def get_expense(expense_id: int) -> dict | None:
    with _lock:
        return _row(conn().execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone())


def find_by_invoice(invoice_no: str) -> dict | None:
    with _lock:
        return _row(conn().execute("SELECT * FROM expenses WHERE invoice_no = ?", (invoice_no,)).fetchone())


def delete_expense(expense_id: int) -> dict | None:
    with _lock:
        row = get_expense(expense_id)
        conn().execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        conn().commit()
        return row


def _month_filter(month: str | None) -> tuple[str, list]:
    # Pending uploads have no date yet; keep them visible in every month.
    if not month:
        return "1=1", []
    return "(date LIKE ? OR date IS NULL)", [f"{month}-%"]


def list_expenses(month: str | None = None, category: str | None = None, q: str | None = None) -> list[dict]:
    where, args = _month_filter(month)
    if category:
        where += " AND category = ?"
        args.append(category)
    if q:
        where += " AND (merchant LIKE ? OR note LIKE ? OR items LIKE ? OR invoice_no LIKE ?)"
        args += [f"%{q}%"] * 4
    with _lock:
        rows = conn().execute(
            f"SELECT * FROM expenses WHERE {where} ORDER BY (date IS NULL) DESC, date DESC, id DESC", args
        ).fetchall()
    return [_row(r) for r in rows]


def summary(month: str) -> dict:
    with _lock:
        c = conn()
        by_cat = c.execute(
            "SELECT category, SUM(amount) total, COUNT(*) n FROM expenses "
            "WHERE date LIKE ? AND status NOT IN ('processing', 'error') GROUP BY category ORDER BY total DESC",
            (f"{month}-%",),
        ).fetchall()
        daily = c.execute(
            "SELECT date, SUM(amount) total FROM expenses WHERE date LIKE ? AND status NOT IN ('processing', 'error') "
            "GROUP BY date ORDER BY date",
            (f"{month}-%",),
        ).fetchall()
        pending = c.execute(
            "SELECT COUNT(*) FROM expenses WHERE status IN ('processing', 'review', 'error')"
        ).fetchone()[0]
    y, m = map(int, month.split("-"))
    prev = f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"
    with _lock:
        prev_total = conn().execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE date LIKE ? AND status NOT IN ('processing', 'error')", (f"{prev}-%",)
        ).fetchone()[0]
    return {
        "month": month,
        "total": sum((r["total"] or 0) for r in by_cat),
        "count": sum(r["n"] for r in by_cat),
        "previous_total": prev_total,
        "by_category": [{"category": r["category"] or "其他", "total": r["total"] or 0, "count": r["n"]} for r in by_cat],
        "daily": [{"date": r["date"], "total": r["total"] or 0} for r in daily],
        "pending": pending,
    }


def remember_merchant(key: str, merchant: str | None, category: str | None) -> None:
    if not key:
        return
    with _lock:
        c = conn()
        c.execute(
            "INSERT INTO merchant_rules(key, merchant, category) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET merchant = COALESCE(excluded.merchant, merchant), "
            "category = COALESCE(excluded.category, category)",
            (key, merchant or None, category or None),
        )
        c.commit()


def backfill_merchant(seller_tax_id: str, merchant: str) -> None:
    with _lock:
        c = conn()
        c.execute(
            "UPDATE expenses SET merchant = ?, "
            "status = CASE WHEN status = 'review' AND message LIKE '第一次遇到%' THEN 'done' ELSE status END, "
            "message = CASE WHEN message LIKE '第一次遇到%' THEN '' ELSE message END "
            "WHERE seller_tax_id = ? AND (merchant IS NULL OR merchant = '' OR merchant LIKE '統編 %')",
            (merchant, seller_tax_id),
        )
        c.commit()


def lookup_merchant(key: str | None) -> dict | None:
    if not key:
        return None
    with _lock:
        r = conn().execute("SELECT * FROM merchant_rules WHERE key = ?", (key,)).fetchone()
    return dict(r) if r else None


def pending_ids() -> list[int]:
    with _lock:
        return [r["id"] for r in conn().execute("SELECT id FROM expenses WHERE status = 'processing'")]
