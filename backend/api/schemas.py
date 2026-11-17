"""API 請求／回應資料格式。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class RectModel(BaseModel):
    x: int
    y: int
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class ProcessRequest(BaseModel):
    image: str = Field(description="base64 編碼的影像檔 (PNG/JPEG...)")
    params: dict[str, Any] = Field(default_factory=dict)
    roi: RectModel | None = Field(default=None, description="處理範圍；省略則處理整張")


class ViewModel(BaseModel):
    label: str
    image: str = Field(description="base64 編碼的 PNG")


class ProcessResponse(BaseModel):
    image: str = Field(description="base64 編碼的 PNG")
    views: list[ViewModel] = Field(default_factory=list, description="要一併顯示的中間結果")
    result_label: str = "結果"


class StrokeRequest(BaseModel):
    image: str = Field(description="base64 編碼的影像檔")
    points: list[tuple[float, float]] = Field(min_length=1, max_length=20000, description="筆畫經過的點 (x, y)")
    size: int = Field(ge=1, le=300, description="筆刷直徑（像素）")
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$", description="顏色，例如 #ff0000")
    source: str | None = Field(
        default=None, description="base64 影像，與 image 同尺寸；提供時改為畫出這張圖的像素（橡皮擦）",
    )
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    seed: int | None = Field(default=None, description="隨機種子（噴槍用），固定後結果可重現")

    @model_validator(mode="after")
    def _color_or_source(self) -> "StrokeRequest":
        if (self.color is None) == (self.source is None):
            raise ValueError("color 與 source 必須擇一提供")
        return self


class StrokeResponse(BaseModel):
    image: str = Field(description="base64 編碼的 PNG")
