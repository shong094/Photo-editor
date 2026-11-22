"""影像工作區：平常顯示單張影像，有中間結果時改為多張並排比較。

最左邊固定是可框選的主畫布，比較模式下顯示處理前的原圖。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from PIL import Image

from .canvas_view import ImageCanvas, PixelSample, Rect

ORIGINAL_LABEL = "原圖"


class Workspace(ttk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        on_selection_change: Callable[[Rect | None], None],
        on_close_comparison: Callable[[], None],
        on_pixel_hover: Callable[[PixelSample | None], None] | None = None,
    ):
        super().__init__(master)
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)
        self._extra: list[tk.Widget] = []
        self._column_count = 1

        self.main_canvas = ImageCanvas(
            self, on_selection_change=on_selection_change, on_pixel_hover=on_pixel_hover,
        )
        self.main_canvas.grid(row=2, column=0, sticky="nsew")

        self._close_button = ttk.Button(self, text="返回單圖編輯", command=on_close_comparison)
        self._main_label = ttk.Label(self, text=ORIGINAL_LABEL, anchor="center")

    def show_single(self, image: Image.Image | None, keep_selection: bool = True) -> None:
        self._clear_comparison()
        self.main_canvas.grid_configure(padx=0)
        self.main_canvas.set_image(image, keep_selection=keep_selection)

    def show_comparison(self, original: Image.Image, panes: list[tuple[str, Image.Image]]) -> None:
        """並排顯示：原圖 | panes[0] | panes[1] ..."""
        self._clear_comparison()
        self._column_count = len(panes) + 1
        for col in range(self._column_count):
            self.columnconfigure(col, weight=1, uniform="pane")

        self._close_button.grid(row=0, column=0, columnspan=self._column_count, sticky="e", padx=4, pady=4)
        self._main_label.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        self.main_canvas.grid_configure(padx=4)
        self.main_canvas.set_image(original, keep_selection=True)

        for col, (label, image) in enumerate(panes, start=1):
            title = ttk.Label(self, text=label, anchor="center")
            title.grid(row=1, column=col, sticky="ew", pady=(0, 4))
            canvas = ImageCanvas(self, selectable=False)
            canvas.grid(row=2, column=col, sticky="nsew", padx=4)
            canvas.set_image(image)
            self._extra += [title, canvas]

    def _clear_comparison(self) -> None:
        for widget in self._extra:
            widget.destroy()
        self._extra.clear()
        self._close_button.grid_remove()
        self._main_label.grid_remove()
        for col in range(self._column_count):
            self.columnconfigure(col, weight=0, uniform="")
        self.columnconfigure(0, weight=1)
        self._column_count = 1
