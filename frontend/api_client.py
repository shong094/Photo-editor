"""與後端溝通的 HTTP 客戶端。前端只透過這裡存取後端。"""
from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import Any

import requests
from PIL import Image

Rect = tuple[int, int, int, int]  # (x, y, width, height)


class ApiError(Exception):
    pass


@dataclass
class FilterResult:
    image: Image.Image
    views: list[tuple[str, Image.Image]]  # 要一併顯示的中間結果
    result_label: str


class ApiClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: float = 120):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            resp = self.session.request(
                method, f"{self.base_url}{path}", timeout=self.timeout, **kwargs
            )
        except requests.RequestException as e:
            raise ApiError(f"無法連線到後端 ({self.base_url})：{e}") from e
        if not resp.ok:
            try:
                detail = resp.json().get("detail", resp.text)
            except ValueError:
                detail = resp.text
            raise ApiError(f"後端錯誤 {resp.status_code}：{detail}")
        return resp.json()

    def list_filters(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/filters")

    def apply_filter(
        self,
        name: str,
        image: Image.Image,
        params: dict[str, Any],
        roi: Rect | None = None,
    ) -> FilterResult:
        payload: dict[str, Any] = {"image": _encode(image), "params": params}
        if roi is not None:
            x, y, w, h = roi
            payload["roi"] = {"x": x, "y": y, "width": w, "height": h}
        data = self._request("POST", f"/api/filters/{name}", json=payload)
        return FilterResult(
            image=_decode(data["image"]),
            views=[(v["label"], _decode(v["image"])) for v in data["views"]],
            result_label=data["result_label"],
        )


def _encode(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _decode(data: str) -> Image.Image:
    img = Image.open(io.BytesIO(base64.b64decode(data)))
    img.load()
    return img
