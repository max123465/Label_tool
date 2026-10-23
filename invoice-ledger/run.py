import uvicorn

from app import config
from app.main import _local_addresses

if __name__ == "__main__":
    print("\n  發票記帳已啟動，請保持這個視窗開著。\n")
    print(f"  電腦上打開：http://localhost:{config.PORT}")
    for a in _local_addresses():
        label = "Tailscale（出門也能用）" if a["kind"] == "tailscale" else "家裡 Wi-Fi"
        print(f"  手機打開（{label}）：{a['url']}")
    print(f"\n  資料存放位置：{config.DATA_DIR}\n")
    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT, log_level="warning")
