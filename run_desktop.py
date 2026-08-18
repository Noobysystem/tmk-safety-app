import os
import sys
import threading
import time
import webview
import uvicorn

sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))
from backend.main import app

def start_api():
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

if __name__ == "__main__":
    server_thread = threading.Thread(target=start_api, daemon=True)
    server_thread.start()
    time.sleep(1)

    webview.create_window(
        title="ТМК — Охрана труда и Промбезопасность",
        url="http://127.0.0.1:8000",
        width=1300,
        height=850,
        resizable=True
    )
    webview.start()
