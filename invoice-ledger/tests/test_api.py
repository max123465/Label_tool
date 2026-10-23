import time

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from tests.test_einvoice import LEFT, RIGHT, _qr


def _photo() -> bytes:
    canvas = np.full((1200, 800, 3), 240, np.uint8)
    left, right = _qr(LEFT), _qr(RIGHT)
    canvas[600 : 600 + left.shape[0], 80 : 80 + left.shape[1]] = left
    canvas[600 : 600 + right.shape[0], 450 : 450 + right.shape[1]] = right
    return cv2.imencode(".jpg", canvas)[1].tobytes()


def _wait(client, expense_id):
    for _ in range(50):
        e = client.get(f"/api/expenses/{expense_id}").json()
        if e["status"] != "processing":
            return e
        time.sleep(0.1)
    raise AssertionError("still processing")


def test_upload_flow():
    with TestClient(app) as client:
        first = _wait(client, client.post("/api/receipts", files={"file": ("a.jpg", _photo())}).json()["id"])
        assert first["amount"] == 100
        assert first["date"] == "2026-10-23"
        assert first["category"] == "餐飲"
        assert first["status"] == "review"  # new store: asks for its name once

        client.put(f"/api/expenses/{first['id']}", json={"merchant": "全家", "category": "餐飲"})

        assert client.get(f"/api/expenses/{first['id']}").json()["status"] == "done"

        dup = _wait(client, client.post("/api/receipts", files={"file": ("b.jpg", _photo())}).json()["id"])
        assert dup["status"] == "error" and "已經記過" in dup["message"]

        summary = client.get("/api/summary?month=2026-10").json()
        assert summary["total"] == 100

        manual = client.post("/api/expenses", json={"amount": 50, "merchant": "早餐店", "date": "2026-10-23", "category": "餐飲"}).json()
        assert client.get("/api/summary?month=2026-10").json()["total"] == 150

        csv = client.get("/api/export.csv?month=2026-10").content.decode("utf-8-sig")
        assert "全家" in csv and "早餐店" in csv

        client.delete(f"/api/expenses/{manual['id']}")
        assert client.get("/api/summary?month=2026-10").json()["total"] == 100
        assert client.get("/").status_code == 200
        assert client.get("/icon-180.png").headers["content-type"] == "image/png"
