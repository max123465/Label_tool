"""Background queue: one photo at a time so the local model is never overloaded."""

from __future__ import annotations

import logging
import queue
import threading
from datetime import date

import cv2

from . import config, db, ollama
from .classify import classify
from .einvoice import EInvoice, extract_invoices

log = logging.getLogger("ledger.worker")
_queue: "queue.Queue[int]" = queue.Queue()


def enqueue(expense_id: int) -> None:
    _queue.put(expense_id)


def start() -> None:
    for expense_id in db.pending_ids():
        enqueue(expense_id)
    threading.Thread(target=_loop, daemon=True, name="receipt-worker").start()


def _loop() -> None:
    while True:
        expense_id = _queue.get()
        try:
            process(expense_id)
        except Exception as exc:  # keep the worker alive whatever one photo does
            log.exception("processing %s failed", expense_id)
            db.update_expense(expense_id, status="error", message=f"辨識失敗：{exc}")


def _ai_ready() -> bool:
    return ollama.status().get("model_ready", False)


def merchant_key(e: dict) -> str | None:
    if e.get("seller_tax_id"):
        return e["seller_tax_id"]
    if e.get("merchant"):
        return "name:" + e["merchant"].strip()
    return None


def _from_invoice(img, inv: EInvoice, categories: list[str]) -> dict:
    items = [i.to_dict() for i in inv.items]
    rule = db.lookup_merchant(inv.seller_tax_id) or {}
    merchant = rule.get("merchant")
    category = rule.get("category") or classify(merchant, items, categories)
    message = ""

    if not merchant and _ai_ready():
        try:
            known = {"date": inv.date, "total": inv.total_amount, "items": items}
            ai = ollama.read_receipt(img, categories, known)
            merchant = (ai.get("merchant") or "").strip() or None
            if merchant:
                db.remember_merchant(inv.seller_tax_id, merchant, None)
                category = category or classify(merchant, items, categories) or ai.get("category")
        except Exception as exc:
            log.warning("AI merchant lookup failed: %s", exc)

    status = "done"
    if not category:
        category = "其他"
        status = "review"
        message = "無法自動判斷分類，請選一下"
    if not merchant:
        status = "review"
        message = "第一次遇到這家店，填上店名後，以後同一家店會自動帶入"
    return {
        "date": inv.date,
        "merchant": merchant or f"統編 {inv.seller_tax_id}",
        "seller_tax_id": inv.seller_tax_id,
        "invoice_no": inv.invoice_no,
        "amount": inv.total_amount,
        "category": category,
        "items": items,
        "source": "qr",
        "status": status,
        "message": message,
    }


def _from_ai(img, categories: list[str]) -> dict:
    ai = ollama.read_receipt(img, categories)
    merchant = (ai.get("merchant") or "").strip() or None
    items = [i for i in ai.get("items") or [] if i.get("name")]
    rule = db.lookup_merchant("name:" + merchant) if merchant else None
    category = (rule or {}).get("category") or classify(merchant, items, categories) or ai.get("category") or "其他"
    total = ai.get("total") or None
    day = ai.get("date") or ""
    try:
        date.fromisoformat(day)
    except ValueError:
        day = date.today().isoformat()
    return {
        "date": day,
        "merchant": merchant or "未知商家",
        "amount": total,
        "category": category,
        "items": items,
        "source": "ai",
        "status": "review",
        "message": "AI 讀取，請核對金額" if total else "AI 讀不到金額，請手動輸入",
    }


def process(expense_id: int) -> None:
    expense = db.get_expense(expense_id)
    if not expense or expense["status"] != "processing":
        return
    img = cv2.imread(str(config.RECEIPT_DIR / expense["image"]))
    if img is None:
        db.update_expense(expense_id, status="error", message="照片讀不到")
        return

    categories = db.categories()
    invoices = extract_invoices(img)

    if invoices:
        first = True
        for inv in invoices:
            dup = db.find_by_invoice(inv.invoice_no)
            if dup:
                if first:
                    db.update_expense(
                        expense_id, status="error", date=dup["date"], amount=dup["amount"],
                        merchant=dup["merchant"], category=dup["category"],
                        message=f"這張發票 {inv.invoice_no} 已經記過了",
                    )
                    first = False
                continue
            values = _from_invoice(img, inv, categories)
            if first:
                db.update_expense(expense_id, **values)
                first = False
            else:
                db.create_expense(image=expense["image"], thumb=expense["thumb"], **values)
        return

    if _ai_ready():
        db.update_expense(expense_id, **_from_ai(img, categories))
        return

    db.update_expense(
        expense_id,
        date=date.today().isoformat(),
        merchant="",
        category="其他",
        source="manual",
        status="review",
        message="找不到發票 QR code，本機 AI 也還沒裝好，請手動輸入",
    )

