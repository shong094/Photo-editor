"""柔邊筆：中心最濃、往外平滑淡出。"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from ..core.brush import Brush, dab_distance, register_brush


@lru_cache(maxsize=64)
def _soft_dab(size: int) -> np.ndarray:
    t = np.clip(dab_distance(size) / (size / 2), 0, 1)
    return ((1 - t * t) ** 2).astype(np.float32)


@register_brush
class SoftBrush(Brush):
    name = "soft"
    display_name = "柔邊筆"
    description = "邊緣柔和淡出的筆觸，適合上色與陰影。"
    spacing = 0.1

    def dab(self, size: int, rng: np.random.Generator) -> np.ndarray:
        return _soft_dab(size)
