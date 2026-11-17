"""工具面板：切換「框選／筆刷／橡皮擦」，以及筆觸、大小、不透明度與顏色。

筆刷清單由後端提供，後端新增筆刷後這裡會自動出現。
"""
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import colorchooser, ttk
from typing import Any, Callable

PRESET_COLORS = ["#000000", "#ffffff", "#e53935", "#fb8c00", "#fdd835", "#43a047", "#1e88e5", "#8e24aa"]


@dataclass
class BrushSettings:
    brush: str
    size: int
    color: str  # "#rrggbb"
    opacity: float  # 0~1
    erase: bool = False  # 橡皮擦：擦回原圖，不使用 color


class BrushPanel(ttk.LabelFrame):
    def __init__(
        self,
        master: tk.Misc,
        on_tool_change: Callable[[str], None],
        on_settings_change: Callable[[BrushSettings], None],
    ):
        super().__init__(master, text="工具", padding=6)
        self.on_tool_change = on_tool_change
        self.on_settings_change = on_settings_change

        self.tool = tk.StringVar(value="select")
        self.brush = tk.StringVar()
        self.size = tk.IntVar(value=12)
        self.opacity = tk.IntVar(value=100)  # 百分比
        self.color = "#e53935"

        tools = ttk.Frame(self)
        tools.pack(fill="x")
        for value, text in (("select", "框選"), ("brush", "筆刷"), ("eraser", "橡皮擦")):
            ttk.Radiobutton(
                tools, text=text, value=value, variable=self.tool, command=self._tool_changed,
            ).pack(side="left", padx=(0, 8))

        self._brush_options = ttk.Frame(self)
        self._brush_list = ttk.Frame(self._brush_options)
        self._brush_list.pack(fill="x", pady=(6, 2))

        for label, var, lo, hi, step in (("大小", self.size, 1, 200, 1), ("不透明度 %", self.opacity, 5, 100, 5)):
            row = ttk.Frame(self._brush_options)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=label).pack(side="left")
            ttk.Spinbox(row, textvariable=var, from_=lo, to=hi, increment=step, width=6).pack(side="right")
            var.trace_add("write", lambda *_: self._settings_changed())

        # 顏色只有筆刷用得到，橡皮擦時隱藏
        self._color_frame = ttk.Frame(self._brush_options)
        row = ttk.Frame(self._color_frame)
        row.pack(fill="x", pady=(4, 2))
        ttk.Label(row, text="顏色").pack(side="left")
        self._swatch = tk.Button(row, width=4, relief="sunken", bg=self.color, activebackground=self.color,
                                 command=self._pick_color)
        self._swatch.pack(side="right")

        presets = ttk.Frame(self._color_frame)
        presets.pack(fill="x", pady=(2, 0))
        # 平均分配寬度，側欄再窄也排得下
        for i, c in enumerate(PRESET_COLORS):
            presets.columnconfigure(i, weight=1, uniform="swatch")
            tk.Button(presets, width=1, bg=c, activebackground=c, relief="flat", bd=1,
                      command=lambda c=c: self._set_color(c)).grid(row=0, column=i, sticky="ew", padx=1)

    # ---- 公開介面 ----
    def load_brushes(self, brushes: list[dict[str, Any]]) -> None:
        for child in self._brush_list.winfo_children():
            child.destroy()
        for i, b in enumerate(brushes):  # 每列兩個，筆刷變多時自動換行
            ttk.Radiobutton(
                self._brush_list, text=b["display_name"], value=b["name"],
                variable=self.brush, command=self._settings_changed,
            ).grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 12), pady=1)
        if brushes and self.brush.get() not in {b["name"] for b in brushes}:
            self.brush.set(brushes[0]["name"])
        self._settings_changed()

    @property
    def settings(self) -> BrushSettings | None:
        try:
            size = max(1, min(int(self.size.get()), 200))
            opacity = max(5, min(int(self.opacity.get()), 100)) / 100
        except (tk.TclError, ValueError):  # 使用者正在輸入、欄位暫時是空的
            return None
        if not self.brush.get():
            return None
        return BrushSettings(self.brush.get(), size, self.color, opacity, erase=self.tool.get() == "eraser")

    def select_tool(self, tool: str) -> None:
        self.tool.set(tool)
        self._tool_changed()

    # ---- 內部 ----
    def _tool_changed(self) -> None:
        tool = self.tool.get()
        if tool == "select":
            self._brush_options.pack_forget()
        else:
            self._brush_options.pack(fill="x")
        if tool == "brush":
            self._color_frame.pack(fill="x")
        else:
            self._color_frame.pack_forget()
        self.on_tool_change(tool)
        self._settings_changed()

    def _settings_changed(self) -> None:
        s = self.settings
        if s is not None:
            self.on_settings_change(s)

    def _pick_color(self) -> None:
        _, hex_color = colorchooser.askcolor(color=self.color, parent=self, title="選擇筆刷顏色")
        if hex_color:
            self._set_color(hex_color)

    def _set_color(self, color: str) -> None:
        self.color = color.lower()
        self._swatch.config(bg=self.color, activebackground=self.color)
        self._settings_changed()
