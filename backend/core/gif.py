"""把多張圖片串成 GIF 動畫。"""
from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

MAX_FRAMES = 50
MAX_FILE_BYTES = 10 * 1024 * 1024
MIN_DURATION = 20  # 毫秒；更短的值多數瀏覽器會當成 100ms
MAX_DURATION = 60_000
MAX_WIDTH = 4096
MAX_TOTAL_PIXELS = 200_000_000  # 所有幀加總，避免記憶體爆掉
ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP", "GIF"}


@dataclass
class GifFrame:
    data: bytes  # 原始檔案內容
    duration: int  # 毫秒


@dataclass
class GifResult:
    data: bytes
    width: int
    height: int
    frame_count: int


def limits() -> dict[str, int | list[str]]:
    """提供給前端顯示與事先檢查用。"""
    return {
        "max_frames": MAX_FRAMES,
        "max_file_bytes": MAX_FILE_BYTES,
        "min_duration": MIN_DURATION,
        "max_duration": MAX_DURATION,
        "max_width": MAX_WIDTH,
        "formats": sorted(ALLOWED_FORMATS),
    }


def load_frame(data: bytes) -> Image.Image:
    """解碼一張圖片（GIF 只取第一格），轉成 RGBA。"""
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"檔案超過 {MAX_FILE_BYTES // 1024 // 1024}MB")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()  # 多格 GIF 開啟時停在第一格
    except (UnidentifiedImageError, OSError) as e:
        raise ValueError(f"無法解析影像：{e}") from e
    if img.format not in ALLOWED_FORMATS:
        raise ValueError(f"不支援的格式 {img.format}")
    return img.convert("RGBA")


def output_size(first: Image.Image, width: int | None) -> tuple[int, int]:
    """輸出尺寸：寬度預設與第一張相同，高度依第一張的比例。"""
    w, h = first.size
    if width is None:
        return w, h
    return width, max(1, round(h * width / w))


def fit_frame(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """等比例縮放到 size 內並置中，比例不同時周圍留透明。"""
    if img.size == size:
        return img
    scale = min(size[0] / img.width, size[1] / img.height)
    resized = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.paste(resized, ((size[0] - resized.width) // 2, (size[1] - resized.height) // 2))
    return canvas


TRANSPARENT_INDEX = 255


def to_palette(img: Image.Image) -> Image.Image:
    """RGBA 轉成調色盤影像，半透明以下的像素用保留的透明色。

    GIF 的透明只有「全透明／不透明」兩種，透明度要每一幀都標在同一個色號上，
    交給 Pillow 自動轉換的話，第一幀不透明時後面幀的透明會遺失。
    """
    p = img.convert("RGB").quantize(colors=TRANSPARENT_INDEX, method=Image.Quantize.MEDIANCUT)
    palette = p.getpalette()[: TRANSPARENT_INDEX * 3]
    p.putpalette(palette + [0, 0, 0] * (256 - len(palette) // 3))
    transparent = img.getchannel("A").point(lambda a: 255 if a < 128 else 0)
    p.paste(TRANSPARENT_INDEX, mask=transparent)
    p.info["transparency"] = TRANSPARENT_INDEX
    return p


def make_gif(frames: list[GifFrame], play_count: int | None = None, width: int | None = None) -> GifResult:
    """合成 GIF。

    play_count: None 為無限循環，n 為總共播放 n 次。
    width: 輸出寬度，None 則與第一張相同。
    """
    if not 1 <= len(frames) <= MAX_FRAMES:
        raise ValueError(f"圖片數量必須在 1 到 {MAX_FRAMES} 張之間")
    if width is not None and not 1 <= width <= MAX_WIDTH:
        raise ValueError(f"輸出寬度必須在 1 到 {MAX_WIDTH} 之間")
    if play_count is not None and play_count < 1:
        raise ValueError("播放次數至少為 1")

    images = []
    for i, f in enumerate(frames, 1):
        if not MIN_DURATION <= f.duration <= MAX_DURATION:
            raise ValueError(f"第 {i} 張：顯示時間必須在 {MIN_DURATION} 到 {MAX_DURATION} 毫秒之間")
        try:
            images.append(load_frame(f.data))
        except ValueError as e:
            raise ValueError(f"第 {i} 張：{e}") from None

    size = output_size(images[0], width)
    if size[0] * size[1] * len(images) > MAX_TOTAL_PIXELS:
        raise ValueError("輸出影像太大，請縮小輸出寬度或減少圖片數量")
    fitted = [fit_frame(img, size) for img in images]
    options = {"save_all": True, "duration": [f.duration for f in frames], "disposal": 2, "optimize": False}
    # 全部不透明時存成 RGB 交給 Pillow 轉換，不用保留透明色，畫質較好
    if all(img.getextrema()[3][0] == 255 for img in fitted):
        fitted = [img.convert("RGB") for img in fitted]
    else:
        fitted = [to_palette(img) for img in fitted]
        options["transparency"] = TRANSPARENT_INDEX
    options["append_images"] = fitted[1:]
    if play_count is None:
        options["loop"] = 0
    elif play_count > 1:
        options["loop"] = play_count - 1  # GIF 記錄的是「重複」次數；不寫則只播一次
    buf = io.BytesIO()
    fitted[0].save(buf, format="GIF", **options)
    return GifResult(buf.getvalue(), size[0], size[1], len(fitted))
