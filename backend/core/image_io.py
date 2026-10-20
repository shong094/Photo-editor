"""影像與 base64 字串之間的轉換。"""
from __future__ import annotations

import base64
import binascii
import io

import numpy as np
from PIL import Image, UnidentifiedImageError


def decode_image(data_b64: str) -> np.ndarray:
    try:
        raw = base64.b64decode(data_b64, validate=True)
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (binascii.Error, UnidentifiedImageError) as e:
        raise ValueError(f"無法解析影像: {e}") from e
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
    return np.asarray(img).copy()


def encode_image(array: np.ndarray, fmt: str = "PNG") -> str:
    buf = io.BytesIO()
    Image.fromarray(array).save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("ascii")
