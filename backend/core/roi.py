"""在指定區域 (ROI) 內套用功能。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .base import ImageFilter


@dataclass
class Rect:
    x: int
    y: int
    width: int
    height: int

    def clip(self, img_w: int, img_h: int) -> "Rect":
        x0 = max(0, min(self.x, img_w))
        y0 = max(0, min(self.y, img_h))
        x1 = max(0, min(self.x + self.width, img_w))
        y1 = max(0, min(self.y + self.height, img_h))
        return Rect(x0, y0, x1 - x0, y1 - y0)


def apply_filter(
    image: np.ndarray,
    flt: ImageFilter,
    params: dict[str, Any],
    roi: Rect | None = None,
) -> np.ndarray:
    """套用功能。roi 為 None 時處理整張影像。"""
    if roi is None:
        return flt.process(image, **params)

    h, w = image.shape[:2]
    r = roi.clip(w, h)
    if r.width == 0 or r.height == 0:
        raise ValueError("選取範圍不在影像內")

    result = image.copy()
    region = image[r.y : r.y + r.height, r.x : r.x + r.width]
    result[r.y : r.y + r.height, r.x : r.x + r.width] = flt.process(region, **params)
    return result
