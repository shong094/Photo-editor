"""在指定區域 (ROI) 內套用功能。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .base import FilterOutput, ImageFilter


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
) -> FilterOutput:
    """套用功能。roi 為 None 時處理整張影像。

    有 roi 時，結果貼回原圖；中間結果貼到黑底上，讓三者尺寸一致。
    """
    if roi is None:
        return flt.run(image, **params)

    h, w = image.shape[:2]
    r = roi.clip(w, h)
    if r.width == 0 or r.height == 0:
        raise ValueError("選取範圍不在影像內")

    area = (slice(r.y, r.y + r.height), slice(r.x, r.x + r.width))
    output = flt.run(image[area], **params)

    result = image.copy()
    result[area] = output.image

    views = []
    for label, view in output.views:
        canvas = np.zeros_like(image)
        if image.shape[2] == 4:
            canvas[:, :, 3] = image[:, :, 3]
        canvas[area] = view
        views.append((label, canvas))
    return FilterOutput(result, views, output.result_label)
