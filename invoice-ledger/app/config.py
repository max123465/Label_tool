import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("LEDGER_DATA_DIR", ROOT / "data")).resolve()
DB_PATH = DATA_DIR / "ledger.db"
RECEIPT_DIR = DATA_DIR / "receipts"
STATIC_DIR = ROOT / "static"

HOST = os.environ.get("LEDGER_HOST", "0.0.0.0")
PORT = int(os.environ.get("LEDGER_PORT", "8000"))

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5vl:7b")
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT", "300"))
