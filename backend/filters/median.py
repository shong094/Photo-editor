"""中值濾波。"""
from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from ..core.base import ImageFilter, ParamSpec
from ..core.registry import register


def median_filter(image: np.ndarray, kernel_size: int) -> np.ndarray:
    """對每個通道做 kernel_size x kernel_size 的中值濾波，邊界以鏡射補齊。"""
    pad = kernel_size // 2
    out = np.empty_like(image)
    for c in range(image.shape[2]):
        channel = np.pad(image[:, :, c], pad, mode="symmetric")
        windows = sliding_window_view(channel, (kernel_size, kernel_size))
        out[:, :, c] = np.median(windows, axis=(-2, -1)).astype(image.dtype)
    return out


@register
class MedianFilter(ImageFilter):
    name = "median"
    display_name = "中值濾波"
    category = "濾波"
    description = "以鄰域中值取代像素值，可有效去除椒鹽雜訊並保留邊緣。"
    params = [
        ParamSpec(
            name="kernel_size",
            label="核大小",
            type="int",
            default=3,
            min=3,
            max=15,
            step=2,
        ),
    ]

    def process(self, image: np.ndarray, kernel_size: int = 3) -> np.ndarray:
        if kernel_size % 2 == 0:
            raise ValueError("核大小必須是奇數")
        alpha = None
        if image.shape[2] == 4:  # 透明通道不處理
            image, alpha = image[:, :, :3], image[:, :, 3:]
        result = median_filter(image, kernel_size)
        if alpha is not None:
            result = np.concatenate([result, alpha], axis=2)
        return result
