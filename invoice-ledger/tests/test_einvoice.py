import cv2
import numpy as np
import pytest

from app.classify import DEFAULT_CATEGORIES, classify
from app.einvoice import extract_invoices, parse_left, parse_right

LEFT = (
    "AB12345678" "1151023" "1234" f"{95:08x}" f"{100:08x}" "00000000" "12345678" + "A" * 24
    + ":**********:3:3:1:鮮奶茶:1:55:御飯糰:1:35"
)
RIGHT = "**洗髮精:1:10"


def test_parse_left():
    inv = parse_left(LEFT)
    assert inv.invoice_no == "AB12345678"
    assert inv.date == "2026-10-23"
    assert inv.total_amount == 100
    assert inv.sales_amount == 95
    assert inv.seller_tax_id == "12345678"
    assert [i.name for i in inv.items] == ["鮮奶茶", "御飯糰"]
    assert inv.items[0].price == 55


def test_parse_left_base64_items():
    import base64

    items = base64.b64encode("拿鐵:2:65".encode()).decode()
    code = LEFT.split(":")[0] + f":**********:1:1:2:{items}"
    inv = parse_left(code)
    assert inv.items[0].name == "拿鐵" and inv.items[0].qty == 2


def test_rejects_non_invoice():
    assert parse_left("https://example.com") is None
    assert parse_right("hello", "1") == []


def test_parse_right():
    assert parse_right(RIGHT, "1")[0].name == "洗髮精"


def _qr(text: str) -> np.ndarray:
    qrcode = pytest.importorskip("qrcode")
    q = qrcode.QRCode(box_size=4, border=2)
    q.add_data(text.encode("utf-8"))
    q.make(fit=True)
    img = np.array(q.make_image().convert("L"))
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)


def test_extract_from_photo_like_image():
    left, right = _qr(LEFT), _qr(RIGHT)
    canvas = np.full((1400, 900, 3), 235, np.uint8)
    cv2.putText(canvas, "E-INVOICE", (200, 150), cv2.FONT_HERSHEY_SIMPLEX, 2, (30, 30, 30), 4)
    canvas[700 : 700 + left.shape[0], 120 : 120 + left.shape[1]] = left
    canvas[700 : 700 + right.shape[0], 520 : 520 + right.shape[1]] = right
    noisy = cv2.GaussianBlur(canvas, (3, 3), 0)

    invoices = extract_invoices(noisy)
    assert len(invoices) == 1
    inv = invoices[0]
    assert inv.total_amount == 100
    assert [i.name for i in inv.items] == ["鮮奶茶", "御飯糰", "洗髮精"]


def test_classify():
    cats = DEFAULT_CATEGORIES
    assert classify(None, [{"name": "鮮奶茶", "qty": 1, "price": 55}], cats) == "餐飲"
    assert classify("全家便利商店", [{"name": "舒潔衛生紙", "qty": 1, "price": 199}], cats) == "日用品"
    assert classify(None, [{"name": "95無鉛汽油", "qty": 30, "price": 31}], cats) == "交通"
    assert classify(None, [{"name": "XYZ", "qty": 1, "price": 1}], cats) is None
