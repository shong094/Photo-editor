import numpy as np

from backend import filters
from backend.core.registry import get_filter
from backend.core.roi import Rect, apply_filter
from backend.filters.conversion import (
    MODE_BLACK_WHITE,
    MODE_GRAYSCALE,
    MODE_NEGATIVE,
    MODE_PALETTE,
    luminance,
)

filters.load_all()


def _color_image():
    return np.array(
        [
            [[255, 0, 0], [0, 255, 0], [0, 0, 255]],
            [[10, 20, 30], [128, 128, 128], [250, 240, 230]],
        ],
        np.uint8,
    )


def test_grayscale_repeats_luminance_to_rgb_channels():
    img = _color_image()
    out = get_filter("image_conversion").process(img, mode=MODE_GRAYSCALE)
    expected = np.repeat(luminance(img)[:, :, None], 3, axis=2)
    assert np.array_equal(out, expected)
    assert np.array_equal(out[:, :, 0], out[:, :, 1])
    assert np.array_equal(out[:, :, 1], out[:, :, 2])


def test_black_white_uses_threshold():
    img = _color_image()
    out = get_filter("image_conversion").process(img, mode=MODE_BLACK_WHITE, threshold=100)
    assert set(np.unique(out)) <= {0, 255}
    assert tuple(out[0, 0]) == (0, 0, 0)  # red luminance is 76
    assert tuple(out[0, 1]) == (255, 255, 255)  # green luminance is 150


def test_negative_inverts_rgb_channels():
    img = _color_image()
    out = get_filter("image_conversion").process(img, mode=MODE_NEGATIVE)
    assert np.array_equal(out, 255 - img)


def test_palette_limits_number_of_colors():
    img = np.array(
        [[[r, g, 128] for r in range(0, 256, 32) for g in range(0, 256, 64)]],
        np.uint8,
    ).reshape(8, 4, 3)
    out = get_filter("image_conversion").process(img, mode=MODE_PALETTE, palette_colors=4)
    colors = {tuple(pixel) for row in out for pixel in row}
    assert len(colors) <= 4


def test_alpha_preserved_for_all_modes():
    img = np.dstack([_color_image(), np.full((2, 3), 77, np.uint8)])
    flt = get_filter("image_conversion")
    for mode in (MODE_GRAYSCALE, MODE_BLACK_WHITE, MODE_PALETTE, MODE_NEGATIVE):
        out = flt.process(img, mode=mode)
        assert out.shape == img.shape
        assert (out[:, :, 3] == 77).all()


def test_roi_only_changes_selected_region():
    img = np.tile(_color_image(), (5, 5, 1))
    flt = get_filter("image_conversion")
    out = apply_filter(img, flt, {"mode": MODE_NEGATIVE, "threshold": 128, "palette_colors": 16}, Rect(1, 1, 4, 3)).image
    outside = np.ones(img.shape[:2], bool)
    outside[1:4, 1:5] = False
    assert np.array_equal(out[outside], img[outside])
    assert np.array_equal(out[1:4, 1:5], 255 - img[1:4, 1:5])


def test_param_validation():
    flt = get_filter("image_conversion")
    assert flt.validate_params({}) == {
        "mode": MODE_GRAYSCALE,
        "threshold": 128,
        "palette_colors": 16,
    }
    for bad in (
        {"mode": "sepia"},
        {"threshold": 300},
        {"palette_colors": 1},
        {"foo": 1},
    ):
        try:
            flt.validate_params(bad)
        except ValueError:
            continue
        raise AssertionError(f"should reject {bad}")
