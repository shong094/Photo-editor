"""註冊表：集中管理所有可用的影像處理功能與筆刷。"""
from __future__ import annotations

from typing import Generic, TypeVar

from .base import ImageFilter

T = TypeVar("T")


class Registry(Generic[T]):
    """以 name 為鍵存放外掛實例。kind 只用於錯誤訊息。"""

    def __init__(self, kind: str):
        self.kind = kind
        self._items: dict[str, T] = {}

    def register(self, cls: type[T]) -> type[T]:
        """類別裝飾器，將外掛加入註冊表。"""
        instance = cls()
        if not instance.name:
            raise ValueError(f"{cls.__name__} 未設定 name")
        if instance.name in self._items:
            raise ValueError(f"{self.kind}名稱重複: {instance.name}")
        self._items[instance.name] = instance
        return cls

    def get(self, name: str) -> T:
        try:
            return self._items[name]
        except KeyError:
            raise KeyError(f"找不到{self.kind}: {name}") from None

    def all(self) -> list[T]:
        return list(self._items.values())


_filters: Registry[ImageFilter] = Registry("功能")

register = _filters.register
get_filter = _filters.get
list_filters = _filters.all
