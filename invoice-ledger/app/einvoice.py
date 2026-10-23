"""Taiwan e-invoice (電子發票證明聯) QR code decoding and parsing.

Left QR layout (財政部 電子發票證明聯一維及二維條碼規格):
  [0:10]  invoice number, e.g. AB12345678
  [10:17] date in ROC calendar, yyyMMdd
  [17:21] random code
  [21:29] sales amount before tax, hex
  [29:37] total amount, hex
  [37:45] buyer tax id (00000000 when none)
  [45:53] seller tax id
  [53:77] encrypted verification
  then ":" separated: reserved, items in QR, total items, encoding, name:qty:price...
Right QR starts with "**" and continues name:qty:price...
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field

import cv2
import numpy as np

LEFT_RE = re.compile(r"^[A-Z]{2}\d{8}\d{7}\d{4}[0-9A-Fa-f]{16}\d{16}")


@dataclass
class InvoiceItem:
    name: str
    qty: float
    price: float

    def to_dict(self) -> dict:
        return {"name": self.name, "qty": self.qty, "price": self.price}


@dataclass
class EInvoice:
    invoice_no: str
    date: str
    random_code: str
    sales_amount: int
    total_amount: int
    buyer_tax_id: str
    seller_tax_id: str
    total_item_count: int | None = None
    encoding: str | None = None
    items: list[InvoiceItem] = field(default_factory=list)


def _to_float(value: str) -> float | None:
    try:
        return float(value.strip())
    except ValueError:
        return None


def _parse_items(fields: list[str]) -> list[InvoiceItem]:
    items = []
    for i in range(0, len(fields) - 2, 3):
        name = fields[i].strip()
        qty = _to_float(fields[i + 1])
        price = _to_float(fields[i + 2])
        if name and qty is not None and price is not None:
            items.append(InvoiceItem(name=name, qty=qty, price=price))
    return items


def _fix_big5(text: str) -> str:
    try:
        return text.encode("latin-1").decode("big5")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def _decode_item_text(text: str, encoding: str | None) -> str:
    if encoding == "2":
        try:
            return base64.b64decode(text).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return text
    if encoding == "0":
        return _fix_big5(text)
    return text


def parse_left(code: str) -> EInvoice | None:
    code = code.strip()
    if not LEFT_RE.match(code):
        return None
    roc = code[10:17]
    try:
        year = int(roc[0:3]) + 1911
        month = int(roc[3:5])
        day = int(roc[5:7])
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return None
        sales = int(code[21:29], 16)
        total = int(code[29:37], 16)
    except ValueError:
        return None

    inv = EInvoice(
        invoice_no=code[0:10],
        date=f"{year:04d}-{month:02d}-{day:02d}",
        random_code=code[17:21],
        sales_amount=sales,
        total_amount=total,
        buyer_tax_id=code[37:45],
        seller_tax_id=code[45:53],
    )

    rest = code[77:]
    parts = rest.split(":")
    # parts: ['', reserved, items_in_qr, total_items, encoding, name, qty, price, ...]
    if len(parts) >= 5:
        inv.encoding = parts[4].strip() or None
        try:
            inv.total_item_count = int(parts[3])
        except ValueError:
            pass
        item_text = ":".join(parts[5:])
        item_text = _decode_item_text(item_text, inv.encoding)
        inv.items = _parse_items(item_text.split(":"))
    return inv


def parse_right(code: str, encoding: str | None) -> list[InvoiceItem]:
    if not code.startswith("**"):
        return []
    text = _decode_item_text(code[2:].lstrip(":"), encoding)
    return _parse_items(text.split(":"))


_wechat = None


def _wechat_detector():
    global _wechat
    if _wechat is None:
        try:
            _wechat = cv2.wechat_qrcode_WeChatQRCode()
        except (AttributeError, cv2.error):
            _wechat = False
    return _wechat


def _resize_long_edge(img: np.ndarray, target: int) -> np.ndarray:
    h, w = img.shape[:2]
    scale = target / max(h, w)
    if abs(scale - 1) < 0.05:
        return img
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    return cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=interp)


def decode_qr_codes(img: np.ndarray) -> list[str]:
    """Return every distinct QR payload found, trying several scales and detectors."""
    found: list[str] = []

    def add(values):
        for v in values:
            if v and v not in found:
                found.append(v)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    variants = [gray, _resize_long_edge(gray, 1600), _resize_long_edge(gray, 2400)]
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    variants.append(clahe.apply(variants[1]))

    wechat = _wechat_detector()
    standard = cv2.QRCodeDetector()
    for v in variants:
        if wechat:
            try:
                res, _ = wechat.detectAndDecode(v)
                add(res)
            except cv2.error:
                pass
        try:
            ok, decoded, _, _ = standard.detectAndDecodeMulti(v)
            if ok:
                add(decoded)
        except cv2.error:
            pass
        if any(LEFT_RE.match(x) for x in found) and any(x.startswith("**") for x in found):
            break
    return found


def extract_invoices(img: np.ndarray) -> list[EInvoice]:
    codes = decode_qr_codes(img)
    lefts = [inv for inv in (parse_left(c) for c in codes) if inv]
    unique: dict[str, EInvoice] = {}
    for inv in lefts:
        unique.setdefault(inv.invoice_no, inv)
    invoices = list(unique.values())

    rights = [c for c in codes if c.startswith("**")]
    if len(invoices) == 1 and rights:
        inv = invoices[0]
        for r in rights:
            inv.items.extend(parse_right(r, inv.encoding))
    return invoices
