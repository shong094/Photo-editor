"""主視窗：組合畫布、功能面板、選單與狀態列。"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from ..api_client import ApiClient, ApiError
from ..document import ImageDocument
from .canvas_view import ImageCanvas, Rect
from .tool_panel import ToolPanel

FILETYPES = [
    ("影像檔", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp"),
    ("所有檔案", "*.*"),
]


class MainWindow:
    def __init__(self, root: tk.Tk, api: ApiClient):
        self.root = root
        self.api = api
        self.doc = ImageDocument()
        self._results: queue.Queue[Callable[[], None]] = queue.Queue()
        self._busy = False

        root.title("影像編輯軟體")
        root.geometry("1100x720")
        self._build_menu()
        self._build_layout()
        self._bind_keys()
        self.root.after(50, self._poll_results)
        self._load_filters()

    # ---- 版面 ----
    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="開啟...", accelerator="Ctrl+O", command=self.open_file)
        file_menu.add_command(label="另存新檔...", accelerator="Ctrl+S", command=self.save_file)
        file_menu.add_separator()
        file_menu.add_command(label="結束", command=self.root.destroy)
        menubar.add_cascade(label="檔案", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=False)
        edit_menu.add_command(label="復原", accelerator="Ctrl+Z", command=self.undo)
        edit_menu.add_command(label="重做", accelerator="Ctrl+Y", command=self.redo)
        edit_menu.add_separator()
        edit_menu.add_command(label="取消選取", accelerator="Esc", command=lambda: self.canvas.clear_selection())
        menubar.add_cascade(label="編輯", menu=edit_menu)
        self.root.config(menu=menubar)

    def _build_layout(self) -> None:
        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True)

        self.canvas = ImageCanvas(body, on_selection_change=self._on_selection_change)
        self.canvas.pack(side="left", fill="both", expand=True)

        side = ttk.Frame(body, width=240)
        side.pack(side="right", fill="y")
        side.pack_propagate(False)
        self.tool_panel = ToolPanel(side, on_apply=self.apply_filter)
        self.tool_panel.pack(fill="both", expand=True)

        self.status = tk.StringVar(value="就緒")
        self.selection_info = tk.StringVar(value="")
        bar = ttk.Frame(self.root, relief="sunken", padding=(6, 2))
        bar.pack(fill="x", side="bottom")
        ttk.Label(bar, textvariable=self.status).pack(side="left")
        ttk.Label(bar, textvariable=self.selection_info).pack(side="right")

    def _bind_keys(self) -> None:
        self.root.bind("<Control-o>", lambda e: self.open_file())
        self.root.bind("<Control-s>", lambda e: self.save_file())
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-y>", lambda e: self.redo())
        self.root.bind("<Escape>", lambda e: self.canvas.clear_selection())

    # ---- 背景工作（避免網路請求卡住 UI）----
    def _run_async(self, work: Callable[[], Any], on_done: Callable[[Any], None], busy_text: str) -> None:
        self._set_busy(True, busy_text)

        def task() -> None:
            try:
                result = work()
                self._results.put(lambda: on_done(result))
            except ApiError as e:
                self._results.put(lambda: self._show_error(str(e)))
            finally:
                self._results.put(lambda: self._set_busy(False))

        threading.Thread(target=task, daemon=True).start()

    def _poll_results(self) -> None:
        while True:
            try:
                self._results.get_nowait()()
            except queue.Empty:
                break
        self.root.after(50, self._poll_results)

    def _set_busy(self, busy: bool, text: str = "就緒") -> None:
        self._busy = busy
        self.tool_panel.set_enabled(not busy)
        self.root.config(cursor="watch" if busy else "")
        if busy:
            self.status.set(text)

    def _show_error(self, msg: str) -> None:
        self.status.set("發生錯誤")
        messagebox.showerror("錯誤", msg, parent=self.root)

    # ---- 動作 ----
    def _load_filters(self) -> None:
        def done(filters: list[dict]) -> None:
            self.tool_panel.load_filters(filters)
            self.status.set(f"已連線後端，載入 {len(filters)} 個功能")

        self._run_async(self.api.list_filters, done, "連線後端中...")

    def open_file(self) -> None:
        path = filedialog.askopenfilename(parent=self.root, filetypes=FILETYPES)
        if not path:
            return
        try:
            self.doc.open(path)
        except OSError as e:
            self._show_error(f"無法開啟檔案：{e}")
            return
        self.canvas.set_image(self.doc.image)
        w, h = self.doc.image.size
        self.status.set(f"已開啟 {self.doc.path.name} ({w}x{h})")

    def save_file(self) -> None:
        if self.doc.image is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self.root, defaultextension=".png", filetypes=FILETYPES,
            initialfile=self.doc.path.stem + "_edited.png" if self.doc.path else "",
        )
        if not path:
            return
        try:
            self.doc.save(path)
        except (OSError, ValueError) as e:
            self._show_error(f"無法儲存檔案：{e}")
            return
        self.status.set(f"已儲存 {path}")

    def apply_filter(self, name: str, params: dict[str, Any]) -> None:
        if self._busy:
            return
        if self.doc.image is None:
            messagebox.showinfo("提示", "請先開啟影像", parent=self.root)
            return
        roi = self.canvas.selection
        if roi is None and not messagebox.askyesno(
            "未選取範圍", "尚未框選範圍，是否處理整張影像？", parent=self.root
        ):
            return

        image = self.doc.image

        def done(result) -> None:
            self.doc.update(result)
            self.canvas.set_image(self.doc.image, keep_selection=True)
            self.status.set("處理完成")

        self._run_async(lambda: self.api.apply_filter(name, image, params, roi), done, "處理中...")

    def undo(self) -> None:
        if self.doc.can_undo() and not self._busy:
            self.doc.undo()
            self.canvas.set_image(self.doc.image, keep_selection=True)
            self.status.set("已復原")

    def redo(self) -> None:
        if self.doc.can_redo() and not self._busy:
            self.doc.redo()
            self.canvas.set_image(self.doc.image, keep_selection=True)
            self.status.set("已重做")

    def _on_selection_change(self, rect: Rect | None) -> None:
        if rect is None:
            self.selection_info.set("未選取（拖曳滑鼠框選範圍，右鍵取消）")
        else:
            x, y, w, h = rect
            self.selection_info.set(f"選取範圍：({x}, {y})  {w}x{h}")
