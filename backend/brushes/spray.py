"""噴槍：在筆頭範圍內隨機灑點，像噴漆一樣。"""
from __future__ import annotations

import numpy as np

from ..core.brush import Brush, dab_radius, register_brush

#: 每個筆印灑點數相對於筆頭面積的比例
DENSITY = 0.2


@register_brush
class SprayBrush(Brush):
    name = "spray"
    display_name = "噴槍"
    description = "在筆頭範圍內隨機噴灑細點，拖越久越密。"
    spacing = 0.3

    def dab(self, size: int, rng: np.random.Generator) -> np.ndarray:
        r = dab_radius(size)
        dab = np.zeros((2 * r + 1, 2 * r + 1), np.float32)
        radius = size / 2
        n = max(1, round(DENSITY * np.pi * radius * radius))
        # 在圓內均勻取點：半徑取平方根才不會集中在中心
        dist = radius * np.sqrt(rng.random(n))
        angle = rng.random(n) * 2 * np.pi
        xs = np.clip(np.rint(r + dist * np.cos(angle)).astype(int), 0, 2 * r)
        ys = np.clip(np.rint(r + dist * np.sin(angle)).astype(int), 0, 2 * r)
        dab[ys, xs] = 1
        return dab
