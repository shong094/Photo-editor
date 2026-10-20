"""啟動前端視窗（需先啟動後端）。"""
import argparse
import tkinter as tk

from frontend.api_client import ApiClient
from frontend.ui.main_window import MainWindow

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="http://127.0.0.1:8000", help="後端網址")
    args = parser.parse_args()

    root = tk.Tk()
    MainWindow(root, ApiClient(args.backend))
    root.mainloop()
