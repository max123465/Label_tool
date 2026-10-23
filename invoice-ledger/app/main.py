from __future__ import annotations

import csv
import io
import logging
import socket
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime
from urllib.parse import quote

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, db, icon, ollama, worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.conn()
    worker.start()
    yield


app = FastAPI(title="發票記帳", lifespan=lifespan)
config.RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/receipts", StaticFiles(directory=config.RECEIPT_DIR), name="receipts")
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")


class ExpenseIn(BaseModel):
    date: str | None = None
    merchant: str | None = None
    amount: float | None = None
    category: str | None = None
    note: str | None = None
    remember: bool = True


class CategoryIn(BaseModel):
    name: str


@app.get("/")
def index():
    return FileResponse(config.STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(config.STATIC_DIR / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/favicon.ico")
def favicon():
    return Response(icon.png(192), media_type="image/png", headers={"Cache-Control": "max-age=86400"})


@app.get("/icon-{size}.png")
def app_icon(size: int):
    if size not in (180, 192, 512):
        raise HTTPException(404)
    return Response(icon.png(size), media_type="image/png", headers={"Cache-Control": "max-age=86400"})


def _save_image(data: bytes) -> tuple[str, str]:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(400, "看不懂這個圖片格式，請用 JPG 或 PNG")
    h, w = img.shape[:2]
    if max(h, w) > 3000:
        s = 3000 / max(h, w)
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    folder = datetime.now().strftime("%Y-%m")
    (config.RECEIPT_DIR / folder).mkdir(parents=True, exist_ok=True)
    name = f"{folder}/{datetime.now():%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    cv2.imwrite(str(config.RECEIPT_DIR / f"{name}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    h, w = img.shape[:2]
    s = 360 / max(h, w)
    thumb = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else img
    cv2.imwrite(str(config.RECEIPT_DIR / f"{name}-s.jpg"), thumb, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return f"{name}.jpg", f"{name}-s.jpg"


@app.post("/api/receipts")
async def upload_receipt(file: UploadFile = File(...)):
    data = await file.read()
    if not data:
        raise HTTPException(400, "沒有收到照片")
    image, thumb = _save_image(data)
    expense_id = db.create_expense(image=image, thumb=thumb, status="processing", source="photo")
    worker.enqueue(expense_id)
    return db.get_expense(expense_id)


@app.post("/api/receipts/{expense_id}/retry")
def retry_receipt(expense_id: int):
    e = db.get_expense(expense_id)
    if not e or not e.get("image"):
        raise HTTPException(404)
    db.update_expense(expense_id, status="processing", message="", invoice_no=None)
    worker.enqueue(expense_id)
    return db.get_expense(expense_id)


@app.get("/api/expenses")
def list_expenses(month: str | None = None, category: str | None = None, q: str | None = None):
    return db.list_expenses(month, category, q)


@app.get("/api/expenses/{expense_id}")
def get_expense(expense_id: int):
    e = db.get_expense(expense_id)
    if not e:
        raise HTTPException(404)
    return e


@app.post("/api/expenses")
def create_expense(body: ExpenseIn):
    values = body.model_dump(exclude={"remember"}, exclude_none=True)
    values.setdefault("date", date.today().isoformat())
    values.setdefault("category", "其他")
    expense_id = db.create_expense(source="manual", status="done", **values)
    e = db.get_expense(expense_id)
    if body.remember and e.get("merchant"):
        db.remember_merchant(worker.merchant_key(e), e["merchant"], e["category"])
    return e


@app.put("/api/expenses/{expense_id}")
def update_expense(expense_id: int, body: ExpenseIn):
    before = db.get_expense(expense_id)
    if not before:
        raise HTTPException(404)
    values = body.model_dump(exclude={"remember"}, exclude_none=True)
    if before["status"] in ("review", "error") and values:
        values["status"] = "done"
        values["message"] = ""
    db.update_expense(expense_id, **values)
    after = db.get_expense(expense_id)
    if after.get("seller_tax_id") and body.merchant and not body.merchant.startswith("統編 "):
        db.backfill_merchant(after["seller_tax_id"], body.merchant.strip())
    if body.remember:
        db.remember_merchant(worker.merchant_key(after), after.get("merchant"), after.get("category"))
    return after


@app.delete("/api/expenses/{expense_id}")
def delete_expense(expense_id: int):
    e = db.delete_expense(expense_id)
    if not e:
        raise HTTPException(404)
    still_used = e.get("image") and any(
        x.get("image") == e["image"] for x in db.list_expenses()
    )
    if e.get("image") and not still_used:
        for name in (e["image"], e.get("thumb")):
            if name:
                (config.RECEIPT_DIR / name).unlink(missing_ok=True)
    return {"ok": True}


@app.get("/api/summary")
def summary(month: str | None = None):
    return db.summary(month or date.today().strftime("%Y-%m"))


@app.get("/api/categories")
def get_categories():
    return db.categories()


@app.post("/api/categories")
def add_category(body: CategoryIn):
    name = body.name.strip()
    if not name or len(name) > 12:
        raise HTTPException(400, "分類名稱要 1 到 12 個字")
    db.add_category(name)
    return db.categories()


@app.delete("/api/categories/{name}")
def delete_category(name: str):
    if name == "其他":
        raise HTTPException(400, "「其他」不能刪除")
    db.delete_category(name)
    return db.categories()


def _local_addresses() -> list[dict]:
    ips: set[str] = set()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            ips.add(s.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    out = []
    for ip in sorted(ips):
        if ip.startswith("127."):
            continue
        a, b = (int(x) for x in ip.split(".")[:2])
        kind = "tailscale" if a == 100 and 64 <= b <= 127 else "lan"
        out.append({"kind": kind, "url": f"http://{ip}:{config.PORT}"})
    return out


@app.get("/api/status")
def status():
    return {"ollama": ollama.status(), "addresses": _local_addresses(), "data_dir": str(config.DATA_DIR)}


@app.get("/api/export.csv")
def export_csv(month: str | None = None):
    buf = io.StringIO()
    buf.write("\ufeff")  # BOM so Excel opens Chinese text correctly
    w = csv.writer(buf)
    w.writerow(["日期", "商家", "分類", "金額", "發票號碼", "統編", "品項", "備註"])
    for e in db.list_expenses(month):
        if e["status"] in ("processing", "error"):
            continue
        items = "、".join(f"{i['name']}x{i['qty']:g}" for i in e["items"])
        w.writerow([e["date"], e["merchant"], e["category"], e["amount"], e["invoice_no"] or "",
                    e["seller_tax_id"] or "", items, e["note"] or ""])
    name = f"記帳-{month or '全部'}.csv"
    return StreamingResponse(
        iter([buf.getvalue().encode("utf-8")]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"},
    )
