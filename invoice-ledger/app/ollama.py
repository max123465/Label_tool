"""Local vision model through Ollama (https://ollama.com). Nothing leaves the PC."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request

import cv2
import numpy as np

from . import config


def _request(path: str, payload: dict | None = None, timeout: float = 5) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        config.OLLAMA_URL.rstrip("/") + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if data else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def status() -> dict:
    try:
        tags = _request("/api/tags", timeout=2)
    except (urllib.error.URLError, OSError, ValueError):
        return {"running": False, "model": config.OLLAMA_MODEL, "model_ready": False}
    names = [m.get("name", "") for m in tags.get("models", [])]
    wanted = config.OLLAMA_MODEL
    ready = any(n == wanted or n == f"{wanted}:latest" or n.split(":")[0] == wanted for n in names)
    return {"running": True, "model": wanted, "model_ready": ready, "installed": names}


def _image_b64(img: np.ndarray, long_edge: int = 1280) -> str:
    h, w = img.shape[:2]
    scale = long_edge / max(h, w)
    if scale < 1:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    if not ok:
        raise ValueError("cannot encode image")
    return base64.b64encode(buf.tobytes()).decode()


SCHEMA = {
    "type": "object",
    "properties": {
        "merchant": {"type": "string"},
        "date": {"type": "string"},
        "total": {"type": "number"},
        "category": {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "qty": {"type": "number"},
                    "price": {"type": "number"},
                },
                "required": ["name", "qty", "price"],
            },
        },
    },
    "required": ["merchant", "date", "total", "category", "items"],
}


def read_receipt(img: np.ndarray, categories: list[str], known: dict | None = None) -> dict:
    """Ask the vision model to read a Taiwanese receipt. `known` holds facts from the QR code."""
    hint = ""
    if known:
        hint = (
            "\n已從 QR code 確定的資料（請直接沿用，不要更改）："
            + json.dumps(known, ensure_ascii=False)
            + "\n你只需要讀出商家名稱並判斷分類。"
        )
    prompt = (
        "這是一張台灣的發票或收據照片。請讀出以下資訊並只回傳 JSON：\n"
        "- merchant：商店名稱（例如「全家便利商店」「全聯福利中心」），用繁體中文\n"
        "- date：消費日期，格式 YYYY-MM-DD。發票上的民國年要加 1911 換成西元年\n"
        "- total：總金額（新台幣，數字）\n"
        "- items：品項列表，每項有 name、qty、price（單價）\n"
        f"- category：從這些分類中選一個最適合的：{'、'.join(categories)}\n"
        "看不清楚的欄位填空字串或 0，不要亂猜。" + hint
    )
    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt, "images": [_image_b64(img)]}],
        "stream": False,
        "format": SCHEMA,
        "options": {"temperature": 0},
    }
    resp = _request("/api/chat", payload, timeout=config.OLLAMA_TIMEOUT)
    content = resp.get("message", {}).get("content", "{}")
    data = json.loads(content)
    if data.get("category") not in categories:
        data["category"] = None
    return data
