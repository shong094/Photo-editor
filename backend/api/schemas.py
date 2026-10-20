"""API 請求／回應資料格式。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RectModel(BaseModel):
    x: int
    y: int
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class ProcessRequest(BaseModel):
    image: str = Field(description="base64 編碼的影像檔 (PNG/JPEG...)")
    params: dict[str, Any] = Field(default_factory=dict)
    roi: RectModel | None = Field(default=None, description="處理範圍；省略則處理整張")


class ProcessResponse(BaseModel):
    image: str = Field(description="base64 編碼的 PNG")
