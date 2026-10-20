"""功能註冊表：集中管理所有可用的影像處理功能。"""
from __future__ import annotations

from .base import ImageFilter

_REGISTRY: dict[str, ImageFilter] = {}


def register(cls: type[ImageFilter]) -> type[ImageFilter]:
    """類別裝飾器，將功能加入註冊表。"""
    instance = cls()
    if not instance.name:
        raise ValueError(f"{cls.__name__} 未設定 name")
    if instance.name in _REGISTRY:
        raise ValueError(f"功能名稱重複: {instance.name}")
    _REGISTRY[instance.name] = instance
    return cls


def get_filter(name: str) -> ImageFilter:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise KeyError(f"找不到功能: {name}") from None


def list_filters() -> list[ImageFilter]:
    return list(_REGISTRY.values())
