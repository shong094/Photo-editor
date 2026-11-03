"""邊緣偵測子：拉普拉斯銳利濾波。"""
from __future__ import annotations

import numpy as np

from ..core.base import FilterOutput, ImageFilter, ParamSpec
from ..core.registry import register

# 中心為負的拉普拉斯核，因此銳利化是 g = f - c * laplacian(f)
KERNELS = {
    "4": np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]]),
    "8": np.array([[1, 1, 1], [1, -8, 1], [1, 1, 1]]),
}


def laplacian(image: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """對每個通道做 3x3 摺積，邊界以鏡射補齊。回傳有正負號的 int32 陣列。"""
    h, w, channels = image.shape
    out = np.zeros(image.shape, np.int32)
    for c in range(channels):
        padded = np.pad(image[:, :, c], 1, mode="symmetric").astype(np.int32)
        for (i, j), weight in np.ndenumerate(kernel):
            if weight:
                out[:, :, c] += weight * padded[i : i + h, j : j + w]
    return out


@register
class LaplacianFilter(ImageFilter):
    name = "laplacian"
    display_name = "邊緣偵測子（拉普拉斯）"
    category = "銳利濾波"
    description = "以拉普拉斯濾波取出邊緣，再疊加回原圖達到銳利化。"
    params = [
        ParamSpec(
            name="neighbors",
            label="鄰域",
            type="choice",
            default="4",
            choices=list(KERNELS),
        ),
        ParamSpec(
            name="strength",
            label="疊加強度",
            type="float",
            default=1.0,
            min=0.0,
            max=3.0,
            step=0.1,
        ),
    ]

    def run(self, image: np.ndarray, neighbors: str = "4", strength: float = 1.0) -> FilterOutput:
        alpha = None
        if image.shape[2] == 4:  # 透明通道不處理
            image, alpha = image[:, :, :3], image[:, :, 3:]

        response = laplacian(image, KERNELS[neighbors])
        edges = np.clip(np.abs(response), 0, 255).astype(np.uint8)
        sharpened = np.clip(image - strength * response, 0, 255).astype(np.uint8)

        if alpha is not None:
            edges = np.concatenate([edges, alpha], axis=2)
            sharpened = np.concatenate([sharpened, alpha], axis=2)
        return FilterOutput(sharpened, [("拉普拉斯濾波", edges)], "疊加結果")

    def process(self, image: np.ndarray, neighbors: str = "4", strength: float = 1.0) -> np.ndarray:
        return self.run(image, neighbors, strength).image
