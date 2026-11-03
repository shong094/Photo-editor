"""單一執行檔的進入點：在背景執行緒啟動後端，再開啟前端視窗。

前後端仍然透過 HTTP 溝通（只是跑在同一個程序裡），架構不變。
"""
import os
import socket
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox

# 打包成無主控台視窗時 stdout/stderr 為 None，uvicorn 寫 log 會出錯
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import uvicorn  # noqa: E402

from backend.app import app  # noqa: E402
from frontend.api_client import ApiClient, ApiError  # noqa: E402
from frontend.ui.main_window import MainWindow  # noqa: E402


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_backend(port: int) -> uvicorn.Server:
    config = uvicorn.Config(
        app, host="127.0.0.1", port=port,
        log_config=None, access_log=False,
        loop="asyncio", http="h11", ws="none", lifespan="off",
    )
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()
    return server


def _wait_ready(api: ApiClient, timeout: float = 15) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            api.list_filters()
            return True
        except ApiError:
            time.sleep(0.1)
    return False


def main() -> None:
    port = _free_port()
    server = _start_backend(port)
    api = ApiClient(f"http://127.0.0.1:{port}")

    root = tk.Tk()
    if not _wait_ready(api):
        root.withdraw()
        messagebox.showerror("錯誤", "後端啟動失敗")
        return
    MainWindow(root, api)
    root.mainloop()
    server.should_exit = True


if __name__ == "__main__":
    main()
