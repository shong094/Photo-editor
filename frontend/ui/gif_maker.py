"""製作 GIF 視窗：選擇多張圖片、調整每幀時間與順序，交給後端合成 GIF 後下載。

版面：左邊是圖片來源與每幀設定，右邊是預覽與輸出選項。
拖放檔案需要 tkinterdnd2，沒有安裝時拖放區只能點擊選檔。
"""
from __future__ import annotations

import io
import os
import tkinter as tk
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from PIL import Image, ImageSequence, ImageTk, UnidentifiedImageError

from ..api_client import ApiClient, ApiError, GifCreated

# ---- 外觀 ----
BG = "#f5f7fa"
CARD = "#ffffff"
BORDER = "#dde3ea"
TEXT = "#1f2937"
MUTED = "#6b7280"
DASH = "#c7cfd9"
ACCENT = "#2563eb"
ACCENT_HOVER = "#1d4ed8"
ACCENT_DISABLED = "#93b4ee"
FONT = ("Microsoft JhengHei UI", 10)
FONT_BOLD = ("Microsoft JhengHei UI", 10, "bold")
FONT_SMALL = ("Microsoft JhengHei UI", 9)
FONT_BIG = ("Microsoft JhengHei UI", 11, "bold")

INPUT_STYLE = dict(
    font=FONT, fg=TEXT, relief="flat", bd=4,
    highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT,
)

PREVIEW_SIZE = (460, 280)
THUMB_SIZE = 48
DEFAULT_DURATION = 200

# 後端回傳前先用的預設值，與 backend/core/gif.py 一致
DEFAULT_LIMITS = {
    "max_frames": 50,
    "max_file_bytes": 10 * 1024 * 1024,
    "min_duration": 20,
    "max_duration": 60_000,
    "max_width": 4096,
    "formats": ["GIF", "JPEG", "PNG", "WEBP"],
}
FILETYPES = [("圖片", "*.png *.jpg *.jpeg *.webp *.gif"), ("所有檔案", "*.*")]


@dataclass
class FrameItem:
    name: str
    data: bytes  # 原始檔案，原封不動送給後端
    preview: Image.Image  # 縮小過的 RGBA，只用於預覽
    thumb: ImageTk.PhotoImage
    duration: tk.StringVar


class Animator:
    """在 Label 上依序播放影像，每幀停留各自的毫秒數。"""

    def __init__(self, label: tk.Label):
        self.label = label
        self._frames: list[tuple[ImageTk.PhotoImage, int]] = []
        self._index = 0
        self._job: str | None = None

    def play(self, frames: list[tuple[Image.Image, int]]) -> None:
        self.stop()
        self._frames = [(ImageTk.PhotoImage(img), max(20, d)) for img, d in frames]
        self._index = 0
        if self._frames:
            self._show()

    def stop(self) -> None:
        if self._job is not None:
            self.label.after_cancel(self._job)
            self._job = None
        self._frames = []

    def _show(self) -> None:
        photo, duration = self._frames[self._index]
        self.label.config(image=photo, text="")
        self._index = (self._index + 1) % len(self._frames)
        if len(self._frames) > 1:
            self._job = self.label.after(duration, self._show)


class PlaceholderEntry(tk.Entry):
    """空白時顯示灰色提示文字的輸入框。"""

    def __init__(self, master: tk.Misc, placeholder: str, **kwargs: Any):
        super().__init__(master, **kwargs)
        self.placeholder = placeholder
        self._fg = kwargs.get("fg", TEXT)
        self._showing = False
        self.bind("<FocusIn>", lambda e: self._hide())
        self.bind("<FocusOut>", lambda e: self._show_placeholder())
        self._show_placeholder()

    def value(self) -> str:
        return "" if self._showing else self.get().strip()

    def clear(self) -> None:
        self.delete(0, "end")
        self._showing = False
        if self.focus_get() is not self:
            self._show_placeholder()

    def _show_placeholder(self) -> None:
        if not self.get():
            self._showing = True
            self.insert(0, self.placeholder)
            self.config(fg=MUTED)

    def _hide(self) -> None:
        if self._showing:
            self.delete(0, "end")
            self.config(fg=self._fg)
            self._showing = False


def _card(master: tk.Misc) -> tk.Frame:
    return tk.Frame(master, bg=CARD, highlightbackground=BORDER, highlightthickness=1, padx=20, pady=16)


def _label(master: tk.Misc, text: str = "", font=FONT, fg=TEXT, **kwargs: Any) -> tk.Label:
    return tk.Label(master, text=text, font=font, fg=fg, bg=master["bg"], **kwargs)


def _fit(img: Image.Image, box: tuple[int, int]) -> Image.Image:
    img = img.copy()
    img.thumbnail(box, Image.LANCZOS)
    return img


class GifMakerWindow(tk.Toplevel):
    def __init__(self, master: tk.Misc, api: ApiClient):
        super().__init__(master, bg=BG)
        self.api = api
        self.limits = dict(DEFAULT_LIMITS)
        self.frames: list[FrameItem] = []
        self.result: GifCreated | None = None
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._busy = False
        self._playing: list | None = None  # 正在預覽的內容，沒變就不重播

        self.title("製作 GIF")
        self.geometry("1100x760")
        self.minsize(900, 640)
        self.protocol("WM_DELETE_WINDOW", self.close)

        self.columnconfigure(0, weight=5, uniform="col")
        self.columnconfigure(1, weight=7, uniform="col")
        self.rowconfigure(0, weight=1)
        self._build_source_card().grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=16)
        self._build_output_card().grid(row=0, column=1, sticky="new", padx=(8, 16), pady=16)

        self._rebuild_list()
        self._refresh()
        self._run(self.api.gif_limits, self._on_limits)

    # ================= 版面：左側（圖片來源） =================
    def _build_source_card(self) -> tk.Frame:
        card = _card(self)

        top = tk.Frame(card, bg=CARD)
        top.pack(fill="x")
        reset = _label(top, "⟲  重置圖像和設置", font=FONT_SMALL, fg=MUTED, cursor="hand2")
        reset.pack(side="right")
        reset.bind("<Button-1>", lambda e: self.reset())
        reset.bind("<Enter>", lambda e: reset.config(fg=TEXT))
        reset.bind("<Leave>", lambda e: reset.config(fg=MUTED))

        _label(card, "影像檔案", font=FONT_BOLD).pack(anchor="w", pady=(4, 6))
        self.drop_zone = tk.Canvas(card, height=150, bg=CARD, highlightthickness=0, cursor="hand2")
        self.drop_zone.pack(fill="x")
        self.drop_zone.bind("<Configure>", lambda e: self._draw_drop_zone())
        self.drop_zone.bind("<Button-1>", lambda e: self.choose_files())
        self.drop_zone.bind("<Enter>", lambda e: self._draw_drop_zone(hover=True))
        self.drop_zone.bind("<Leave>", lambda e: self._draw_drop_zone())
        self._can_drop = self._enable_drop(self.drop_zone)

        self.hint = _label(card, font=FONT_SMALL, fg=MUTED, justify="left", anchor="w")
        self.hint.pack(fill="x", pady=(8, 12))
        card.bind("<Configure>", lambda e: self.hint.config(wraplength=max(200, e.width - 40)), add="+")

        _label(card, "所有幀的顯示時間（毫秒）", font=FONT_BOLD).pack(anchor="w")
        row = tk.Frame(card, bg=CARD)
        row.pack(fill="x", pady=(6, 2))
        self.default_duration = tk.StringVar(value=str(DEFAULT_DURATION))
        tk.Entry(
            row, textvariable=self.default_duration, **INPUT_STYLE, width=10,
        ).pack(side="left", fill="x", expand=True, ipady=6)
        border = tk.Frame(row, bg=BORDER, padx=1, pady=1)  # tk.Button 的 solid 邊框在 Windows 是黑色，改用外框
        border.pack(side="left", padx=(10, 0), fill="y")
        self.apply_all_button = tk.Button(
            border, text="套用到所有幀", font=FONT, relief="flat", bd=0, bg="#f8fafc", fg=TEXT,
            activebackground="#eef2f7", disabledforeground="#a3acb8", padx=14, cursor="hand2",
            command=self.apply_duration_to_all,
        )
        self.apply_all_button.pack(fill="both", expand=True)
        _label(card, "新加入的圖片也會使用這個時間", font=FONT_SMALL, fg=MUTED).pack(anchor="w", pady=(2, 10))

        header = tk.Frame(card, bg=CARD)
        header.pack(fill="x")
        self.frame_count_label = _label(header, font=FONT_BOLD)
        self.frame_count_label.pack(side="left")
        _label(header, "可調整順序與每幀時間", font=FONT_SMALL, fg=MUTED).pack(side="right")

        # 可捲動的幀清單
        holder = tk.Frame(card, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        holder.pack(fill="both", expand=True, pady=(6, 0))
        self.list_canvas = tk.Canvas(holder, bg=CARD, highlightthickness=0, height=120)
        scrollbar = ttk.Scrollbar(holder, orient="vertical", command=self.list_canvas.yview)
        self.list_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.list_canvas.pack(side="left", fill="both", expand=True)
        self.list_frame = tk.Frame(self.list_canvas, bg=CARD)
        window = self.list_canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.list_frame.bind(
            "<Configure>", lambda e: self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all")),
        )
        self.list_canvas.bind("<Configure>", lambda e: self.list_canvas.itemconfigure(window, width=e.width))
        self.list_canvas.bind("<Enter>", lambda e: self.bind_all("<MouseWheel>", self._on_wheel))
        self.list_canvas.bind("<Leave>", lambda e: self.unbind_all("<MouseWheel>"))
        return card

    def _draw_drop_zone(self, hover: bool = False) -> None:
        c = self.drop_zone
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 10:
            return
        color = ACCENT if hover else DASH
        c.create_rectangle(2, 2, w - 2, h - 2, outline=color, dash=(6, 4), width=2,
                           fill="#f8fbff" if hover else CARD)
        # 上傳圖示：箭頭 + 托盤
        cx, cy = w // 2, h // 2 - 28
        icon = "#4b5563"
        c.create_line(cx, cy + 14, cx, cy - 16, fill=icon, width=3, capstyle="round")
        c.create_line(cx - 11, cy - 5, cx, cy - 16, cx + 11, cy - 5, fill=icon, width=3,
                      capstyle="round", joinstyle="round")
        c.create_line(cx - 20, cy + 4, cx - 20, cy + 20, cx + 20, cy + 20, cx + 20, cy + 4, fill=icon,
                      width=3, capstyle="round", joinstyle="round")
        mb = self.limits["max_file_bytes"] // 1024 // 1024
        c.create_text(cx, cy + 46, text="拖放或點擊" if self._can_drop else "點擊選擇圖片", font=FONT, fill=TEXT)
        c.create_text(cx, cy + 70, text=f"最大大小：{mb}MB", font=FONT_SMALL, fill=MUTED)

    # ================= 版面：右側（預覽與輸出） =================
    def _build_output_card(self) -> tk.Frame:
        card = _card(self)

        box = tk.Frame(card, bg=CARD, height=PREVIEW_SIZE[1] + 20)
        box.pack(fill="x")
        box.pack_propagate(False)
        self.preview = tk.Label(box, bg=CARD, fg=MUTED, font=FONT)
        self.preview.pack(expand=True)
        self.animator = Animator(self.preview)
        self.preview_caption = _label(card, font=FONT_SMALL, fg=MUTED)
        self.preview_caption.pack(pady=(4, 0))

        tk.Frame(card, bg=BORDER, height=1).pack(fill="x", pady=14)

        options = tk.Frame(card, bg=CARD)
        options.pack(fill="x")
        options.columnconfigure(0, weight=1, uniform="opt")
        options.columnconfigure(1, weight=1, uniform="opt")

        loop = tk.Frame(options, bg=CARD)
        loop.grid(row=0, column=0, sticky="nw")
        _label(loop, "循環播放", font=FONT_BOLD).pack(anchor="w")
        radios = tk.Frame(loop, bg=CARD)
        radios.pack(anchor="w", pady=(6, 0))
        self.loop_mode = tk.StringVar(value="infinite")
        self.play_count = tk.StringVar(value="3")
        for value, text in (("infinite", "無限"), ("count", "指定次數")):
            tk.Radiobutton(
                radios, text=text, value=value, variable=self.loop_mode, font=FONT, bg=CARD, fg=TEXT,
                activebackground=CARD, command=self._on_option_change,
            ).pack(side="left", padx=(0, 8))
        self.count_spin = ttk.Spinbox(radios, from_=1, to=1000, textvariable=self.play_count, width=5)
        self.count_spin.pack(side="left")
        _label(radios, "次", font=FONT).pack(side="left", padx=(4, 0))
        self.play_count.trace_add("write", lambda *_: self._on_option_change())

        width = tk.Frame(options, bg=CARD)
        width.grid(row=0, column=1, sticky="new")
        _label(width, "輸出寬度（像素）", font=FONT_BOLD).pack(anchor="w")
        self.width_entry = PlaceholderEntry(
            width, "與第一張圖片相同", **INPUT_STYLE,
        )
        self.width_entry.pack(fill="x", pady=(6, 0), ipady=6)
        self.width_entry.bind("<KeyRelease>", lambda e: self._on_option_change(), add="+")

        self.status = _label(card, font=FONT_SMALL, fg=MUTED, anchor="e")
        self.status.pack(fill="x", pady=(16, 6))

        self.create_button = tk.Button(
            card, text="✨  建立 GIF", font=FONT_BIG, fg="white", bg=ACCENT, activebackground=ACCENT_HOVER,
            activeforeground="white", disabledforeground="white", relief="flat", bd=0, cursor="hand2",
            command=self.create_gif,
        )
        self.create_button.pack(fill="x", ipady=8)

        self.download_frame = tk.Frame(card, bg=ACCENT, padx=1, pady=1)
        self.download_button = tk.Button(
            self.download_frame, text="⬇  下載 GIF", font=FONT_BIG, fg=ACCENT, bg=CARD, activebackground="#eff5ff",
            activeforeground=ACCENT, relief="flat", bd=0, cursor="hand2", command=self.download,
        )
        self.download_button.pack(fill="x", ipady=7)
        return card

    # ================= 圖片管理 =================
    def choose_files(self) -> None:
        if self._busy:
            return
        paths = filedialog.askopenfilenames(parent=self, title="選擇要串成 GIF 的圖片", filetypes=FILETYPES)
        if paths:
            self.add_files(paths)

    def add_files(self, paths: list[str] | tuple[str, ...]) -> None:
        """加入圖片（依檔名順序），不符合限制的檔案略過並一次列出原因。"""
        duration = self._default_duration()
        errors: list[str] = []
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            for path in sorted(paths, key=lambda p: os.path.basename(p).lower()):
                name = os.path.basename(path)
                if len(self.frames) >= self.limits["max_frames"]:
                    errors.append(f"最多 {self.limits['max_frames']} 張圖片，其餘未加入")
                    break
                try:
                    self.frames.append(self._load(path, duration))
                except ValueError as e:
                    errors.append(f"{name}：{e}")
        finally:
            self.config(cursor="")
        self._on_frames_change()
        if errors:
            messagebox.showwarning("部分圖片未加入", "\n".join(errors), parent=self)

    def _load(self, path: str, duration: int) -> FrameItem:
        try:
            size = os.path.getsize(path)
            if size > self.limits["max_file_bytes"]:
                raise ValueError(f"檔案超過 {self.limits['max_file_bytes'] // 1024 // 1024}MB")
            with open(path, "rb") as f:
                data = f.read()
            img = Image.open(io.BytesIO(data))
            img.load()  # GIF 只取第一格
        except (OSError, UnidentifiedImageError) as e:
            raise ValueError(f"無法讀取（{e.__class__.__name__}）") from None
        if img.format not in self.limits["formats"]:
            raise ValueError(f"不支援的格式 {img.format}")
        preview = _fit(img.convert("RGBA"), PREVIEW_SIZE)
        thumb = ImageTk.PhotoImage(_fit(preview, (THUMB_SIZE, THUMB_SIZE)), master=self)
        var = tk.StringVar(master=self, value=str(duration))
        var.trace_add("write", lambda *_: self._on_frames_change(rebuild=False))
        return FrameItem(os.path.basename(path), data, preview, thumb, var)

    def _move(self, index: int, delta: int) -> None:
        j = index + delta
        if 0 <= j < len(self.frames):
            self.frames[index], self.frames[j] = self.frames[j], self.frames[index]
            self._on_frames_change()

    def _remove(self, index: int) -> None:
        del self.frames[index]
        self._on_frames_change()

    def apply_duration_to_all(self) -> None:
        duration = self._default_duration(show_error=True)
        if duration is None:
            return
        for item in self.frames:
            item.duration.set(str(duration))

    def reset(self) -> None:
        if self._busy:
            return
        self.frames.clear()
        self.default_duration.set(str(DEFAULT_DURATION))
        self.loop_mode.set("infinite")
        self.play_count.set("3")
        self.width_entry.clear()
        self._on_frames_change()

    def _rebuild_list(self) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()
        if not self.frames:
            _label(self.list_frame, "尚未加入圖片", font=FONT_SMALL, fg=MUTED).pack(pady=16)
            return
        last = len(self.frames) - 1
        for i, item in enumerate(self.frames):
            row = tk.Frame(self.list_frame, bg=CARD, pady=4, padx=6)
            row.pack(fill="x")
            _label(row, f"{i + 1}", font=FONT_SMALL, fg=MUTED, width=2).pack(side="left")
            tk.Label(row, image=item.thumb, bg=CARD, width=THUMB_SIZE, height=THUMB_SIZE).pack(side="left", padx=6)
            for text, command, enabled in (
                ("✕", lambda i=i: self._remove(i), True),
                ("↓", lambda i=i: self._move(i, 1), i < last),
                ("↑", lambda i=i: self._move(i, -1), i > 0),
            ):
                tk.Button(
                    row, text=text, font=FONT_SMALL, width=2, relief="flat", bg="#f1f4f8", fg=TEXT,
                    activebackground="#e2e8f0", state="normal" if enabled else "disabled", command=command,
                ).pack(side="right", padx=1)
            # 檔名一行、顯示時間一行，檔名才不會被擠掉
            info = tk.Frame(row, bg=CARD)
            info.pack(side="left", fill="x", expand=True, padx=(0, 8))
            _label(info, item.name, font=FONT_SMALL, anchor="w").pack(fill="x")
            timing = tk.Frame(info, bg=CARD)
            timing.pack(anchor="w", pady=(2, 0))
            _label(timing, "顯示", font=FONT_SMALL, fg=MUTED).pack(side="left", padx=(0, 4))
            ttk.Spinbox(
                timing, from_=self.limits["min_duration"], to=self.limits["max_duration"], increment=50,
                textvariable=item.duration, width=7,
            ).pack(side="left")
            _label(timing, "毫秒", font=FONT_SMALL, fg=MUTED).pack(side="left", padx=(4, 0))
            if i < last:
                tk.Frame(self.list_frame, bg="#eef1f5", height=1).pack(fill="x")

    def _on_wheel(self, event: tk.Event) -> None:
        self.list_canvas.yview_scroll(int(-event.delta / 120), "units")

    # ================= 輸入檢查 =================
    def _parse_int(self, text: str, lo: int, hi: int) -> int | None:
        try:
            value = int(text.strip())
        except ValueError:
            return None
        return value if lo <= value <= hi else None

    def _default_duration(self, show_error: bool = False) -> int | None:
        lo, hi = self.limits["min_duration"], self.limits["max_duration"]
        value = self._parse_int(self.default_duration.get(), lo, hi)
        if value is None:
            if show_error:
                messagebox.showerror("顯示時間錯誤", f"請輸入 {lo} 到 {hi} 之間的整數（毫秒）", parent=self)
                return None
            return DEFAULT_DURATION
        return value

    def _collect_settings(self) -> tuple[list[int], int | None, int | None] | str:
        """讀取所有設定；有錯誤時回傳錯誤訊息。"""
        lo, hi = self.limits["min_duration"], self.limits["max_duration"]
        durations = []
        for i, item in enumerate(self.frames, 1):
            d = self._parse_int(item.duration.get(), lo, hi)
            if d is None:
                return f"第 {i} 張的顯示時間必須是 {lo} 到 {hi} 之間的整數（毫秒）"
            durations.append(d)
        play_count = None
        if self.loop_mode.get() == "count":
            play_count = self._parse_int(self.play_count.get(), 1, 1000)
            if play_count is None:
                return "播放次數必須是 1 到 1000 之間的整數"
        width = None
        if self.width_entry.value():
            width = self._parse_int(self.width_entry.value(), 1, self.limits["max_width"])
            if width is None:
                return f"輸出寬度必須是 1 到 {self.limits['max_width']} 之間的整數，或留空"
        return durations, play_count, width

    # ================= 狀態更新 =================
    def _on_frames_change(self, rebuild: bool = True) -> None:
        if rebuild:
            self._rebuild_list()
        self.result = None
        self._refresh()

    def _on_option_change(self) -> None:
        self.result = None
        self._refresh()

    def _refresh(self) -> None:
        """依目前狀態更新預覽、提示文字與按鈕。"""
        n = len(self.frames)
        limits = self.limits
        mb = limits["max_file_bytes"] // 1024 // 1024
        self.hint.config(
            text=f"PNG、JPEG、WebP 或 GIF 格式（GIF 僅使用第一格）/ 單張圖片最大 {mb}MB / "
                 f"最多 {limits['max_frames']} 張圖片。尺寸不同的圖片會等比例縮放並置中。"
        )
        self.frame_count_label.config(text=f"圖片（{n} / {limits['max_frames']}）")
        self.count_spin.state(["!disabled"] if self.loop_mode.get() == "count" else ["disabled"])
        self.apply_all_button.config(state="normal" if n and not self._busy else "disabled")

        settings = self._collect_settings()
        if self.result is not None:
            r = self.result
            self.status.config(text="GIF 已建立，可以下載", fg="#15803d")
            self.preview_caption.config(
                text=f"成品預覽：{r.width}×{r.height}，{r.frame_count} 幀，{len(r.data) / 1024:,.0f} KB",
            )
        elif n == 0:
            self.animator.stop()
            self._playing = None
            self.preview.config(image="", text="新增圖片後，此處將顯示預覽。")
            self.preview_caption.config(text="")
            self.status.config(text="新增圖片以建立 GIF 動畫", fg=MUTED)
        else:
            if isinstance(settings, str):
                self.status.config(text=settings, fg="#b91c1c")
            else:
                self.status.config(text=f"共 {n} 張圖片，按下按鈕建立 GIF", fg=MUTED)
            self._play_frames(settings)

        can_create = n > 0 and not isinstance(settings, str) and not self._busy
        self.create_button.config(
            state="normal" if can_create else "disabled",
            bg=ACCENT if can_create else ACCENT_DISABLED,
            text="建立中..." if self._busy else "✨  建立 GIF",
        )
        if self.result is not None:
            self.download_frame.pack(fill="x", pady=(10, 0))
        else:
            self.download_frame.pack_forget()

    def _play_frames(self, settings: tuple | str) -> None:
        """建立 GIF 前的預覽：直接播放加入的圖片。"""
        durations = (
            settings[0] if not isinstance(settings, str)
            else [self._parse_int(f.duration.get(), 1, 10**6) or DEFAULT_DURATION for f in self.frames]
        )
        signature = [(id(f), d) for f, d in zip(self.frames, durations)]
        if self._playing == signature:
            return  # 內容沒變就不要從頭重播
        self._playing = signature
        self.animator.play([(f.preview, d) for f, d in zip(self.frames, durations)])
        self.preview_caption.config(text=f"預覽（{len(self.frames)} 幀，實際尺寸依輸出設定）")

    # ================= 建立與下載 =================
    def create_gif(self) -> None:
        settings = self._collect_settings()
        if self._busy or not self.frames or isinstance(settings, str):
            return
        durations, play_count, width = settings
        frames = [(f.data, d) for f, d in zip(self.frames, durations)]

        def done(result: GifCreated) -> None:
            self.result = result
            self._playing = None
            gif = Image.open(io.BytesIO(result.data))
            self.animator.play([
                (_fit(frame.convert("RGBA"), PREVIEW_SIZE), frame.info.get("duration", DEFAULT_DURATION))
                for frame in ImageSequence.Iterator(gif)
            ])
            self._refresh()

        self._run(lambda: self.api.make_gif(frames, play_count, width), done)

    def download(self) -> None:
        if self.result is None:
            return
        first = os.path.splitext(self.frames[0].name)[0] if self.frames else "animation"
        path = filedialog.asksaveasfilename(
            parent=self, title="儲存 GIF", defaultextension=".gif",
            filetypes=[("GIF 動畫", "*.gif")], initialfile=f"{first}.gif",
        )
        if not path:
            return
        try:
            with open(path, "wb") as f:
                f.write(self.result.data)
        except OSError as e:
            messagebox.showerror("無法儲存", str(e), parent=self)
            return
        self.status.config(text=f"已儲存到 {path}", fg="#15803d")

    # ================= 背景工作 =================
    def _run(self, work: Callable[[], Any], on_done: Callable[[Any], None]) -> None:
        self._busy = True
        self._refresh()
        future = self._executor.submit(work)
        self.after(50, self._poll, future, on_done)

    def _poll(self, future: Future, on_done: Callable[[Any], None]) -> None:
        if not self.winfo_exists():  # 視窗已關閉
            return
        if not future.done():
            self.after(50, self._poll, future, on_done)
            return
        self._busy = False
        try:
            on_done(future.result())
        except ApiError as e:
            messagebox.showerror("錯誤", str(e), parent=self)
        except Exception as e:  # noqa: BLE001 — 錯誤一定要讓使用者看到，不能讓視窗卡在忙碌狀態
            messagebox.showerror("錯誤", f"{type(e).__name__}: {e}", parent=self)
        self._refresh()

    def _on_limits(self, limits: dict[str, Any]) -> None:
        self.limits.update(limits)
        self._draw_drop_zone()

    # ================= 拖放 =================
    def _enable_drop(self, widget: tk.Widget) -> bool:
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD

            TkinterDnD._require(self)
            widget.drop_target_register(DND_FILES)
        except Exception:  # noqa: BLE001 — 沒裝或載入失敗就只提供點擊選檔
            return False

        def on_drop(event: Any) -> str:
            self._draw_drop_zone()
            if not self._busy:
                self.add_files(self.tk.splitlist(event.data))
            return event.action

        widget.dnd_bind("<<Drop>>", on_drop)
        widget.dnd_bind("<<DropEnter>>", lambda e: (self._draw_drop_zone(hover=True), e.action)[1])
        widget.dnd_bind("<<DropLeave>>", lambda e: (self._draw_drop_zone(), e.action)[1])
        return True

    def close(self) -> None:
        self.animator.stop()
        self._executor.shutdown(wait=False, cancel_futures=True)
        self.destroy()
