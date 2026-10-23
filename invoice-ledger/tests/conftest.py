import os
import sys
import tempfile
from pathlib import Path

os.environ["LEDGER_DATA_DIR"] = tempfile.mkdtemp(prefix="ledger-test-")
os.environ["OLLAMA_URL"] = "http://127.0.0.1:9"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
