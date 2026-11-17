"""筆刷的共同介面與筆畫合成。

筆刷只負責「形狀」：給定筆畫經過的點與筆刷大小，產生每個像素的覆蓋率 (0~1)。
顏色與不透明度的合成由 paint_stroke() 統一處理，所以新增筆刷時只要實作 dab()。
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Any, Sequence

import numpy as np

from .registry import Registry

Point = tuple[float, float]  # (x, y)，影像座標


class Brush(ABC):
    """筆刷基底類別。

    筆畫是沿著路徑每隔一小段蓋一個「筆印」(dab)；
    重疊的筆印取最大值，所以同一筆畫內不會越疊越深。
    """

    name: str = ""
    display_name: str = ""
    description: str = ""
    #: 相鄰筆印的間距，相對於筆刷直徑
    spacing: float = 0.15

    @abstractmethod
    def dab(self, size: int, rng: np.random.Generator) -> np.ndarray:
        """回傳單一筆印的覆蓋率：邊長 2*ceil(size/2)+1 的 float32 方陣，中心即筆刷中心。"""

    def coverage(
        self,
        shape: tuple[int, int],
        points: Sequence[Point],
        size: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """整個筆畫在 shape (h, w) 上的覆蓋率。"""
        mask = np.zeros(shape, np.float32)
        step = max(1.0, self.spacing * size)
        for x, y in _resample(points, step):
            _stamp(mask, self.dab(size, rng), x, y)
        return mask

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
        }


brushes: Registry[Brush] = Registry("筆刷")
register_brush = brushes.register


def dab_radius(size: int) -> int:
    return math.ceil(size / 2)


def dab_distance(size: int) -> np.ndarray:
    """筆印方陣中每格到中心的距離。"""
    r = dab_radius(size)
    yy, xx = np.mgrid[-r : r + 1, -r : r + 1]
    return np.hypot(xx, yy).astype(np.float32)


def paint_stroke(
    image: np.ndarray,
    brush: Brush,
    points: Sequence[Point],
    size: int,
    color: tuple[int, int, int] | None = None,
    opacity: float = 1.0,
    seed: int | None = None,
    source: np.ndarray | None = None,
) -> np.ndarray:
    """把一筆畫畫到影像上，回傳新影像。

    color：以純色上色。
    source：改為「畫出」source 對應位置的像素（橡皮擦用原圖當 source，就能擦回原貌）。
    兩者擇一。
    """
    if (color is None) == (source is None):
        raise ValueError("color 與 source 必須擇一提供")
    if source is not None and source.shape != image.shape:
        raise ValueError(f"source 尺寸 {source.shape} 與影像 {image.shape} 不同")

    rng = np.random.default_rng(seed)
    mask = brush.coverage(image.shape[:2], points, size, rng) * opacity
    m = mask[:, :, None]

    out = image.astype(np.float32)
    if source is not None:
        out = out * (1 - m) + source.astype(np.float32) * m
    else:
        out[:, :, :3] = out[:, :, :3] * (1 - m) + np.asarray(color, np.float32) * m
        if image.shape[2] == 4:  # 畫在透明處會讓該處變得不透明
            out[:, :, 3] += mask * (255 - out[:, :, 3])
    return np.clip(np.rint(out), 0, 255).astype(np.uint8)


def _resample(points: Sequence[Point], step: float) -> list[Point]:
    """沿折線每隔 step 取一點（含起點）。"""
    if not points:
        return []
    out = [points[0]]
    carry = 0.0  # 上一段剩下、還沒走完的距離
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        d = step - carry
        while d <= seg:
            t = d / seg
            out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
            d += step
        carry = seg - (d - step)
    return out


def _stamp(mask: np.ndarray, dab: np.ndarray, x: float, y: float) -> None:
    """把筆印以 (x, y) 為中心疊到 mask 上（取最大值），超出邊界的部分會被裁掉。"""
    r = dab.shape[0] // 2
    cx, cy = round(x), round(y)
    h, w = mask.shape
    x0, y0 = max(cx - r, 0), max(cy - r, 0)
    x1, y1 = min(cx + r + 1, w), min(cy + r + 1, h)
    if x0 >= x1 or y0 >= y1:
        return
    sub = dab[y0 - (cy - r) : y1 - (cy - r), x0 - (cx - r) : x1 - (cx - r)]
    np.maximum(mask[y0:y1, x0:x1], sub, out=mask[y0:y1, x0:x1])
