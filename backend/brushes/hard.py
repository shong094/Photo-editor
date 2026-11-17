"""硬邊筆：實心圓形筆頭，邊緣只做一個像素的反鋸齒。"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from ..core.brush import Brush, dab_distance, register_brush


@lru_cache(maxsize=64)
def _hard_dab(size: int) -> np.ndarray:
    return np.clip(size / 2 - dab_distance(size) + 0.5, 0, 1)


@register_brush
class HardBrush(Brush):
    name = "hard"
    display_name = "硬邊筆"
    description = "邊緣清楚的實心筆觸，適合描線。"

    def dab(self, size: int, rng: np.random.Generator) -> np.ndarray:
        return _hard_dab(size)
