"""所有影像處理功能的共同介面。

新增功能時，繼承 ImageFilter、宣告參數、實作 process()，
再用 @register 註冊即可，前端會自動依參數規格產生控制項。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np


@dataclass
class ParamSpec:
    """單一參數的規格，前端依此產生 UI 控制項。"""

    name: str
    label: str
    type: str  # "int" | "float" | "bool" | "choice"
    default: Any
    min: float | None = None
    max: float | None = None
    step: float | None = None
    choices: list[Any] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def coerce(self, value: Any) -> Any:
        """把前端送來的值轉成正確型別並檢查範圍。"""
        if value is None:
            return self.default
        if self.type == "int":
            value = int(value)
        elif self.type == "float":
            value = float(value)
        elif self.type == "bool":
            return bool(value)
        elif self.type == "choice":
            if value not in self.choices:
                raise ValueError(f"參數 {self.name} 必須是 {self.choices} 之一")
            return value
        if self.min is not None and value < self.min:
            raise ValueError(f"參數 {self.name} 不可小於 {self.min}")
        if self.max is not None and value > self.max:
            raise ValueError(f"參數 {self.name} 不可大於 {self.max}")
        return value


class ImageFilter(ABC):
    """影像處理功能基底類別。"""

    #: 唯一識別名稱，用於 API 路徑
    name: str = ""
    #: 顯示在前端的名稱
    display_name: str = ""
    #: 功能分類（之後可用來分組顯示）
    category: str = "其他"
    description: str = ""
    params: list[ParamSpec] = []

    def validate_params(self, raw: dict[str, Any]) -> dict[str, Any]:
        unknown = set(raw) - {p.name for p in self.params}
        if unknown:
            raise ValueError(f"未知參數: {', '.join(sorted(unknown))}")
        return {p.name: p.coerce(raw.get(p.name)) for p in self.params}

    @abstractmethod
    def process(self, image: np.ndarray, **params: Any) -> np.ndarray:
        """處理影像。

        image: HxWxC 的 uint8 陣列（C 為 3 或 4）。
        回傳相同形狀與型別的陣列。
        """

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "category": self.category,
            "description": self.description,
            "params": [p.to_dict() for p in self.params],
        }
