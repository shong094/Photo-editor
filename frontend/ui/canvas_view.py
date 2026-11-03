"""顯示影像並讓使用者用滑鼠框選範圍的畫布。

選取範圍一律以「影像座標」儲存，視窗縮放時會自動重畫。
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable

from PIL import Image, ImageTk

Rect = tuple[int, int, int, int]  # (x, y, width, height)


class ImageCanvas(tk.Canvas):
    def __init__(
        self,
        master: tk.Misc,
        on_selection_change: Callable[[Rect | None], None] | None = None,
        selectable: bool = True,
    ):
        super().__init__(
            master, bg="#2b2b2b", highlightthickness=0, cursor="crosshair" if selectable else "",
        )
        self.on_selection_change = on_selection_change
        self._image: Image.Image | None = None
        self._photo: ImageTk.PhotoImage | None = None
        self._scale = 1.0
        self._offset = (0, 0)
        self._drag_start: tuple[int, int] | None = None
        self._selection: Rect | None = None

        self.bind("<Configure>", lambda e: self._redraw())
        if not selectable:
            return
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Button-3>", lambda e: self.clear_selection())

    # ---- 公開介面 ----
    def set_image(self, image: Image.Image | None, keep_selection: bool = False) -> None:
        self._image = image
        if not keep_selection:
            self._set_selection(None)
        self._redraw()

    @property
    def selection(self) -> Rect | None:
        return self._selection

    def clear_selection(self) -> None:
        self._set_selection(None)
        self._draw_selection()

    # ---- 座標轉換 ----
    def _to_image(self, cx: float, cy: float) -> tuple[int, int]:
        assert self._image is not None
        ox, oy = self._offset
        x = round((cx - ox) / self._scale)
        y = round((cy - oy) / self._scale)
        w, h = self._image.size
        return max(0, min(x, w)), max(0, min(y, h))

    def _to_canvas(self, x: float, y: float) -> tuple[float, float]:
        ox, oy = self._offset
        return x * self._scale + ox, y * self._scale + oy

    # ---- 繪圖 ----
    def _redraw(self) -> None:
        self.delete("all")
        if self._image is None:
            self.create_text(
                self.winfo_width() // 2, self.winfo_height() // 2,
                text="請從「檔案 > 開啟」載入影像", fill="#888", font=("", 14),
            )
            return
        cw, ch = max(self.winfo_width(), 1), max(self.winfo_height(), 1)
        iw, ih = self._image.size
        self._scale = min(cw / iw, ch / ih)
        dw, dh = max(1, int(iw * self._scale)), max(1, int(ih * self._scale))
        self._offset = ((cw - dw) // 2, (ch - dh) // 2)
        resample = Image.LANCZOS if self._scale < 1 else Image.NEAREST
        self._photo = ImageTk.PhotoImage(self._image.resize((dw, dh), resample))
        self.create_image(*self._offset, image=self._photo, anchor="nw")
        self._draw_selection()

    def _draw_selection(self) -> None:
        self.delete("selection")
        if self._selection is None:
            return
        x, y, w, h = self._selection
        x0, y0 = self._to_canvas(x, y)
        x1, y1 = self._to_canvas(x + w, y + h)
        self.create_rectangle(x0, y0, x1, y1, outline="black", width=1, tags="selection")
        self.create_rectangle(x0, y0, x1, y1, outline="white", dash=(4, 4), width=1, tags="selection")

    # ---- 滑鼠事件 ----
    def _on_press(self, event: tk.Event) -> None:
        if self._image is None:
            return
        self._drag_start = self._to_image(event.x, event.y)

    def _on_drag(self, event: tk.Event) -> None:
        if self._drag_start is None:
            return
        self._selection = self._rect_from(self._drag_start, self._to_image(event.x, event.y))
        self._draw_selection()

    def _on_release(self, event: tk.Event) -> None:
        if self._drag_start is None:
            return
        rect = self._rect_from(self._drag_start, self._to_image(event.x, event.y))
        self._drag_start = None
        # 只是點一下（沒拖曳）視為取消選取
        self._set_selection(rect if rect[2] >= 2 and rect[3] >= 2 else None)
        self._draw_selection()

    @staticmethod
    def _rect_from(p0: tuple[int, int], p1: tuple[int, int]) -> Rect:
        x0, x1 = sorted((p0[0], p1[0]))
        y0, y1 = sorted((p0[1], p1[1]))
        return x0, y0, x1 - x0, y1 - y0

    def _set_selection(self, rect: Rect | None) -> None:
        self._selection = rect
        if self.on_selection_change:
            self.on_selection_change(rect)
