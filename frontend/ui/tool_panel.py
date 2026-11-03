"""功能面板：依後端回傳的功能清單與參數規格，自動產生控制項。

後端新增功能後，前端不需修改即可出現在面板上。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable


class ToolPanel(ttk.Frame):
    def __init__(self, master: tk.Misc, on_apply: Callable[[str, dict[str, Any]], None]):
        super().__init__(master, padding=8)
        self.on_apply = on_apply
        self._vars: dict[str, dict[str, tuple[dict, tk.Variable]]] = {}
        self._buttons: list[ttk.Button] = []

    def load_filters(self, filters: list[dict[str, Any]]) -> None:
        for child in self.winfo_children():
            child.destroy()
        self._vars.clear()
        self._buttons.clear()

        # 依分類分組
        groups: dict[str, list[dict]] = {}
        for f in filters:
            groups.setdefault(f.get("category", "其他"), []).append(f)

        for category, items in groups.items():
            group = ttk.LabelFrame(self, text=category, padding=6)
            group.pack(fill="x", pady=(0, 8))
            for f in items:
                self._build_filter(group, f)

    def set_enabled(self, enabled: bool) -> None:
        for b in self._buttons:
            b.state(["!disabled"] if enabled else ["disabled"])

    def _build_filter(self, parent: tk.Misc, spec: dict[str, Any]) -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=4)
        ttk.Label(frame, text=spec["display_name"], font=("", 10, "bold")).pack(anchor="w")
        if spec.get("description"):
            ttk.Label(frame, text=spec["description"], wraplength=200, foreground="#666").pack(anchor="w")

        vars_: dict[str, tuple[dict, tk.Variable]] = {}
        for p in spec["params"]:
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=p["label"]).pack(side="left")
            var = self._make_widget(row, p)
            vars_[p["name"]] = (p, var)
        self._vars[spec["name"]] = vars_

        btn = ttk.Button(frame, text="套用", command=lambda n=spec["name"]: self._apply(n))
        btn.pack(fill="x", pady=(4, 0))
        self._buttons.append(btn)

    @staticmethod
    def _make_widget(parent: tk.Misc, p: dict[str, Any]) -> tk.Variable:
        t = p["type"]
        if t == "bool":
            var = tk.BooleanVar(value=p["default"])
            ttk.Checkbutton(parent, variable=var).pack(side="right")
        elif t == "choice":
            var = tk.StringVar(value=p["default"])
            ttk.Combobox(parent, textvariable=var, values=p["choices"], state="readonly", width=10).pack(side="right")
        else:
            var = tk.IntVar(value=p["default"]) if t == "int" else tk.DoubleVar(value=p["default"])
            ttk.Spinbox(
                parent, textvariable=var, width=8, state="readonly",
                from_=p["min"] if p["min"] is not None else -1e9,
                to=p["max"] if p["max"] is not None else 1e9,
                increment=p["step"] or 1,
                format="%.2f" if t == "float" else "",
            ).pack(side="right")
        return var

    def _apply(self, name: str) -> None:
        params = {pname: var.get() for pname, (_, var) in self._vars[name].items()}
        self.on_apply(name, params)
