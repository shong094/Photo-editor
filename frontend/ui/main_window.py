"""主視窗：組合畫布、功能面板、選單與狀態列。"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from collections import deque
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from ..api_client import ApiClient, ApiError, FilterResult
from ..document import ImageDocument
from .brush_panel import BrushPanel, BrushSettings
from .canvas_view import Point, Rect
from .tool_panel import ToolPanel
from .workspace import Workspace

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
        # 並排比較中的功能與它的輸入影像；調整參數重算時從同一張原圖開始
        self._comparison: tuple[str, Any] | None = None
        # 等待後端處理的筆畫：(預覽 id, 點, 筆刷設定)；一次送一筆，依序處理
        self._strokes: deque[tuple[int, list[Point], BrushSettings]] = deque()

        root.title("影像編輯軟體")
        root.geometry("1280x720")
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

        # 先放側欄，視窗變窄時才不會被工作區擠掉
        side = ttk.Frame(body, width=240)
        side.pack(side="right", fill="y")
        side.pack_propagate(False)
        history = ttk.Frame(side)
        history.pack(fill="x", padx=8, pady=(8, 0))
        self._undo_button = ttk.Button(history, text="↶ 復原", command=self.undo)
        self._redo_button = ttk.Button(history, text="↷ 重做", command=self.redo)
        self._undo_button.pack(side="left", fill="x", expand=True, padx=(0, 2))
        self._redo_button.pack(side="left", fill="x", expand=True, padx=(2, 0))
        self.brush_panel = BrushPanel(
            side, on_tool_change=self._on_tool_change, on_settings_change=self._on_brush_change,
        )
        self.brush_panel.pack(fill="x", padx=8, pady=(8, 0))
        self.tool_panel = ToolPanel(side, on_apply=self.apply_filter)
        self.tool_panel.pack(fill="both", expand=True)

        self.workspace = Workspace(
            body,
            on_selection_change=self._on_selection_change,
            on_close_comparison=self._show_single,
        )
        self.workspace.pack(side="left", fill="both", expand=True)
        self.canvas = self.workspace.main_canvas
        self.canvas.on_stroke = self._queue_stroke

        self.status = tk.StringVar(value="就緒")
        self.selection_info = tk.StringVar(value="")
        bar = ttk.Frame(self.root, relief="sunken", padding=(6, 2))
        bar.pack(fill="x", side="bottom")
        ttk.Label(bar, textvariable=self.status).pack(side="left")
        ttk.Label(bar, textvariable=self.selection_info).pack(side="right")

    def _bind_keys(self) -> None:
        shortcuts = {
            "o": self.open_file,
            "s": self.save_file,
            "z": self.undo,
            "y": self.redo,
            "b": lambda: self.brush_panel.select_tool("brush"),
            "e": lambda: self.brush_panel.select_tool("eraser"),
            "m": lambda: self.brush_panel.select_tool("select"),
        }
        for key, action in shortcuts.items():
            # 大小寫都綁，Caps Lock 開著時快捷鍵才不會失效
            for k in (key, key.upper()):
                self.root.bind(f"<Control-{k}>", lambda e, a=action: a())
        self.root.bind("<Escape>", lambda e: self.canvas.clear_selection())

    # ---- 背景工作（避免網路請求卡住 UI）----
    def _run_async(
        self, work: Callable[[], Any], on_done: Callable[[Any], None], busy_text: str, quiet: bool = False,
    ) -> None:
        """在背景執行 work。quiet 時不切換游標與按鈕狀態（筆刷每畫一筆就會呼叫，避免閃爍）。"""
        self._set_busy(True, busy_text, quiet)

        def task() -> None:
            try:
                result = work()
                self._results.put(lambda: on_done(result))
            except Exception as e:  # noqa: BLE001 — 任何錯誤都要回報，不能讓 UI 卡在忙碌狀態
                # 先轉成字串：except 區塊結束後 e 會被刪除，lambda 稍後才執行
                msg = str(e) if isinstance(e, ApiError) else f"{type(e).__name__}: {e}"
                self._results.put(lambda: self._on_task_error(msg))
            finally:
                self._results.put(lambda: self._set_busy(False, quiet=quiet))

        threading.Thread(target=task, daemon=True).start()

    def _on_task_error(self, msg: str) -> None:
        self._strokes.clear()  # 後面排隊的筆畫多半也會失敗，不要連跳一堆錯誤
        self._show_error(msg)

    def _poll_results(self) -> None:
        try:
            while True:
                try:
                    callback = self._results.get_nowait()
                except queue.Empty:
                    break
                try:
                    callback()
                except Exception as e:  # noqa: BLE001 — 單一回呼出錯不能讓輪詢停掉
                    self._on_task_error(f"內部錯誤：{type(e).__name__}: {e}")
            if not self._busy:
                if self._strokes:
                    self._start_next_stroke()
                else:
                    self.canvas.clear_previews()  # 失敗的筆畫留下的預覽
            self._update_history_buttons()
        finally:
            self.root.after(50, self._poll_results)

    def _update_history_buttons(self) -> None:
        for button, enabled in ((self._undo_button, self.doc.can_undo()), (self._redo_button, self.doc.can_redo())):
            button.state(["!disabled"] if enabled and self._idle else ["disabled"])

    def _set_busy(self, busy: bool, text: str = "就緒", quiet: bool = False) -> None:
        self._busy = busy
        if busy:
            self.status.set(text)
        if quiet:
            return
        self.tool_panel.set_enabled(not busy)
        self.root.config(cursor="watch" if busy else "")

    def _show_error(self, msg: str) -> None:
        self.status.set("發生錯誤")
        messagebox.showerror("錯誤", msg, parent=self.root)

    # ---- 動作 ----
    def _load_filters(self) -> None:
        def done(result: tuple[list[dict], list[dict]]) -> None:
            filters, brushes = result
            self.tool_panel.load_filters(filters)
            self.brush_panel.load_brushes(brushes)
            self.status.set(f"已連線後端，載入 {len(filters)} 個功能、{len(brushes)} 種筆刷")

        self._run_async(lambda: (self.api.list_filters(), self.api.list_brushes()), done, "連線後端中...")

    @property
    def _idle(self) -> bool:
        return not self._busy and not self._strokes

    def open_file(self) -> None:
        path = filedialog.askopenfilename(parent=self.root, filetypes=FILETYPES)
        if not path:
            return
        try:
            self.doc.open(path)
        except OSError as e:
            self._show_error(f"無法開啟檔案：{e}")
            return
        self._show_single(keep_selection=False)
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
        if not self._idle:
            return
        if self.doc.image is None:
            messagebox.showinfo("提示", "請先開啟影像", parent=self.root)
            return
        roi = self.canvas.selection
        if roi is None and not messagebox.askyesno(
            "未選取範圍", "尚未框選範圍，是否處理整張影像？", parent=self.root
        ):
            return

        # 比較模式下重按同一功能：視為調整參數，從原圖重算而不是疊加在結果上
        recompute = self._comparison is not None and self._comparison[0] == name
        image = self._comparison[1] if recompute else self.doc.image

        def done(result: FilterResult) -> None:
            if recompute:
                self.doc.replace(result.image)
            else:
                self.doc.update(result.image)
            if result.views:
                self._comparison = (name, image)
                self.workspace.show_comparison(image, [*result.views, (result.result_label, result.image)])
            else:
                self._show_single()
            self.status.set("處理完成")

        self._run_async(lambda: self.api.apply_filter(name, image, params, roi), done, "處理中...")

    def undo(self) -> None:
        if self.doc.can_undo() and self._idle:
            self.doc.undo()
            self._show_single()
            self.status.set("已復原")

    def redo(self) -> None:
        if self.doc.can_redo() and self._idle:
            self.doc.redo()
            self._show_single()
            self.status.set("已重做")

    # ---- 筆刷 ----
    def _on_tool_change(self, tool: str) -> None:
        self.canvas.set_tool(tool)
        if tool != "select" and self._comparison is not None:
            self._show_single()  # 筆刷畫在目前的結果上，不是比較畫面的原圖

    def _on_brush_change(self, settings: BrushSettings) -> None:
        # 橡皮擦的預覽線用灰色
        self.canvas.set_brush(settings.size, "#9e9e9e" if settings.erase else settings.color)

    def _queue_stroke(self, points: list[Point]) -> None:
        settings = self.brush_panel.settings
        if self.doc.image is None or settings is None:
            return
        if self._comparison is not None:
            self._show_single()
        pid = self.canvas.add_preview(points)
        self._strokes.append((pid, points, settings))

    def _start_next_stroke(self) -> None:
        """送出下一筆。只傳筆畫涵蓋的區塊（並限制在選取範圍內），結果再貼回原圖。"""
        pid, points, s = self._strokes.popleft()
        image = self.doc.image
        pad = s.size / 2 + 2
        x0 = max(0, int(min(x for x, _ in points) - pad))
        y0 = max(0, int(min(y for _, y in points) - pad))
        x1 = min(image.width, int(max(x for x, _ in points) + pad) + 1)
        y1 = min(image.height, int(max(y for _, y in points) + pad) + 1)
        if self.canvas.selection is not None:  # 有框選時只畫在範圍內
            sx, sy, sw, sh = self.canvas.selection
            x0, y0, x1, y1 = max(x0, sx), max(y0, sy), min(x1, sx + sw), min(y1, sy + sh)
        if x0 >= x1 or y0 >= y1:
            self.canvas.remove_preview(pid)
            return

        crop = image.crop((x0, y0, x1, y1))
        local = [(x - x0, y - y0) for x, y in points]
        source = None
        if s.erase:  # 橡皮擦：把開檔時的原圖當成「顏料」畫回去
            original = self.doc.original
            if original is None or original.size != image.size:
                self.canvas.remove_preview(pid)
                self.status.set("沒有可以擦回的原圖")
                return
            source = original.crop((x0, y0, x1, y1)).convert(image.mode)

        def done(painted) -> None:
            self.canvas.remove_preview(pid)
            if self.doc.image is not image:  # 期間開了別的檔案
                return
            new = image.copy()
            new.paste(painted, (x0, y0))
            self.doc.update(new)
            self.canvas.set_image(self.doc.image, keep_selection=True)
            self.status.set("就緒")

        self._run_async(
            lambda: self.api.apply_stroke(s.brush, crop, local, s.size, s.color, s.opacity, source),
            done, "擦除中..." if s.erase else "繪製中...", quiet=True,
        )

    def _show_single(self, keep_selection: bool = True) -> None:
        self._comparison = None
        self.workspace.show_single(self.doc.image, keep_selection=keep_selection)

    def _on_selection_change(self, rect: Rect | None) -> None:
        if rect is None:
            self.selection_info.set("未選取（拖曳滑鼠框選範圍，右鍵取消）")
        else:
            x, y, w, h = rect
            self.selection_info.set(f"選取範圍：({x}, {y})  {w}x{h}")
