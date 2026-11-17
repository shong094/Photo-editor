import base64
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageSequence

from backend.app import app
from backend.core.gif import MAX_FILE_BYTES, MAX_FRAMES, GifFrame, make_gif


def _png(color, size=(40, 30), mode="RGB") -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size, color).save(buf, format="PNG")
    return buf.getvalue()


def _open(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def test_frames_durations_and_infinite_loop():
    frames = [GifFrame(_png(c), d) for c, d in (("red", 100), ("lime", 200), ("blue", 300))]
    result = make_gif(frames)
    gif = _open(result.data)
    assert (result.width, result.height, result.frame_count) == (40, 30, 3)
    assert gif.n_frames == 3
    assert gif.info["loop"] == 0
    durations = [f.info["duration"] for f in ImageSequence.Iterator(gif)]
    assert durations == [100, 200, 300]
    colors = [f.convert("RGB").getpixel((20, 15)) for f in ImageSequence.Iterator(gif)]
    assert colors == [(255, 0, 0), (0, 255, 0), (0, 0, 255)]


@pytest.mark.parametrize("play_count, loop", [(1, None), (3, 2)])
def test_play_count(play_count, loop):
    gif = _open(make_gif([GifFrame(_png("red"), 100), GifFrame(_png("blue"), 100)], play_count=play_count).data)
    assert gif.info.get("loop") == loop


def test_width_resizes_and_letterboxes_other_aspect():
    frames = [GifFrame(_png("red", (200, 100)), 100), GifFrame(_png("blue", (50, 50)), 100)]
    result = make_gif(frames, width=100)
    assert (result.width, result.height) == (100, 50)
    second = list(ImageSequence.Iterator(_open(result.data)))[1].convert("RGBA")
    assert second.getpixel((50, 25))[:3] == (0, 0, 255)  # 置中
    assert second.getpixel((5, 25))[3] == 0  # 兩側透明


def test_transparent_frame_after_opaque_frame_stays_transparent():
    logo = Image.new("RGBA", (60, 60), (0, 0, 0, 0))
    logo.paste((255, 200, 0, 255), (20, 20, 40, 40))
    buf = io.BytesIO()
    logo.save(buf, format="PNG")
    frames = [GifFrame(_png("red", (60, 60)), 100), GifFrame(buf.getvalue(), 100)]
    second = list(ImageSequence.Iterator(_open(make_gif(frames).data)))[1].convert("RGBA")
    assert second.getpixel((5, 5))[3] == 0  # 不能殘留第一幀的紅色
    assert second.getpixel((30, 30)) == (255, 200, 0, 255)


def test_gif_input_uses_first_frame():
    buf = io.BytesIO()
    first, second = Image.new("RGB", (20, 20), "red"), Image.new("RGB", (20, 20), "blue")
    first.save(buf, format="GIF", save_all=True, append_images=[second])
    gif = _open(make_gif([GifFrame(buf.getvalue(), 100)]).data)
    assert gif.convert("RGB").getpixel((10, 10)) == (255, 0, 0)


@pytest.mark.parametrize(
    "frames, message",
    [
        ([], "圖片數量"),
        ([GifFrame(_png("red"), 100)] * (MAX_FRAMES + 1), "圖片數量"),
        ([GifFrame(_png("red"), 5)], "顯示時間"),
        ([GifFrame(b"not an image", 100)], "第 1 張"),
        ([GifFrame(b"0" * (MAX_FILE_BYTES + 1), 100)], "10MB"),
    ],
)
def test_rejects_invalid_input(frames, message):
    with pytest.raises(ValueError, match=message):
        make_gif(frames)


def test_api_roundtrip():
    client = TestClient(app)
    assert client.get("/api/gif/limits").json()["max_frames"] == MAX_FRAMES
    payload = {
        "frames": [{"image": base64.b64encode(_png(c)).decode(), "duration": 150} for c in ("red", "blue")],
        "width": 20,
    }
    data = client.post("/api/gif", json=payload).json()
    assert (data["width"], data["height"], data["frame_count"]) == (20, 15, 2)
    assert _open(base64.b64decode(data["gif"])).format == "GIF"

    bad = client.post("/api/gif", json={"frames": [{"image": "@@@", "duration": 100}]})
    assert bad.status_code == 400
