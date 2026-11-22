"""基本影像轉換：灰階、純黑白、調色盤影像與負片。"""
from __future__ import annotations

import numpy as np
from PIL import Image

from ..core.base import ImageFilter, ParamSpec
from ..core.registry import register

MODE_GRAYSCALE = "灰階"
MODE_BLACK_WHITE = "純黑白"
MODE_PALETTE = "調色盤影像"
MODE_NEGATIVE = "負片"
MODES = [MODE_GRAYSCALE, MODE_BLACK_WHITE, MODE_PALETTE, MODE_NEGATIVE]


def luminance(rgb: np.ndarray) -> np.ndarray:
    """依 Rec. 601 權重計算亮度。"""
    weights = np.array([0.299, 0.587, 0.114], np.float32)
    return np.rint(rgb[:, :, :3].astype(np.float32) @ weights).astype(np.uint8)


def to_grayscale(rgb: np.ndarray) -> np.ndarray:
    gray = luminance(rgb)
    return np.repeat(gray[:, :, None], 3, axis=2)


def to_black_white(rgb: np.ndarray, threshold: int) -> np.ndarray:
    bw = np.where(luminance(rgb) >= threshold, 255, 0).astype(np.uint8)
    return np.repeat(bw[:, :, None], 3, axis=2)


def to_palette(rgb: np.ndarray, colors: int) -> np.ndarray:
    img = Image.fromarray(rgb[:, :, :3], mode="RGB")
    quantized = img.quantize(colors=colors, method=Image.Quantize.MEDIANCUT).convert("RGB")
    return np.asarray(quantized, dtype=np.uint8)


@register
class ImageConversionFilter(ImageFilter):
    name = "image_conversion"
    display_name = "影像轉換"
    category = "影像轉換"
    description = "將彩色影像轉成灰階、純黑白、調色盤影像或負片。"
    params = [
        ParamSpec(
            name="mode",
            label="轉換模式",
            type="choice",
            default=MODE_GRAYSCALE,
            choices=MODES,
        ),
        ParamSpec(
            name="threshold",
            label="黑白門檻",
            type="int",
            default=128,
            min=0,
            max=255,
            step=1,
        ),
        ParamSpec(
            name="palette_colors",
            label="調色盤色彩數",
            type="int",
            default=16,
            min=2,
            max=256,
            step=1,
        ),
    ]

    def process(
        self,
        image: np.ndarray,
        mode: str = MODE_GRAYSCALE,
        threshold: int = 128,
        palette_colors: int = 16,
    ) -> np.ndarray:
        alpha = None
        rgb = image
        if image.shape[2] == 4:
            rgb, alpha = image[:, :, :3], image[:, :, 3:]

        if mode == MODE_GRAYSCALE:
            result = to_grayscale(rgb)
        elif mode == MODE_BLACK_WHITE:
            result = to_black_white(rgb, threshold)
        elif mode == MODE_PALETTE:
            result = to_palette(rgb, palette_colors)
        elif mode == MODE_NEGATIVE:
            result = rgb.copy()
            result[:, :, :3] = 255 - result[:, :, :3]
        else:
            raise ValueError(f"未知轉換模式: {mode}")

        if alpha is not None:
            result = np.concatenate([result, alpha], axis=2)
        return result
