import numpy as np
from PIL import Image, ImageFilter

from backend import filters
from backend.core.registry import get_filter
from backend.core.roi import Rect, apply_filter

filters.load_all()


def _noisy_image(h=40, w=50, seed=0):
    rng = np.random.default_rng(seed)
    img = np.full((h, w, 3), 128, np.uint8)
    mask = rng.random((h, w)) < 0.1
    img[mask] = rng.choice([0, 255], size=(mask.sum(), 1))
    return img


def test_matches_pillow_in_interior():
    img = _noisy_image()
    out = get_filter("median").process(img, kernel_size=5)
    ref = np.asarray(Image.fromarray(img).filter(ImageFilter.MedianFilter(5)))
    assert np.array_equal(out[2:-2, 2:-2], ref[2:-2, 2:-2])


def test_roi_only_changes_selected_region():
    img = _noisy_image()
    flt = get_filter("median")
    out = apply_filter(img, flt, {"kernel_size": 3}, Rect(10, 5, 20, 15)).image
    outside = np.ones(img.shape[:2], bool)
    outside[5:20, 10:30] = False
    assert np.array_equal(out[outside], img[outside])
    assert not np.array_equal(out[5:20, 10:30], img[5:20, 10:30])


def test_alpha_preserved():
    img = np.dstack([_noisy_image(), np.full((40, 50), 77, np.uint8)])
    out = get_filter("median").process(img, kernel_size=3)
    assert out.shape == img.shape
    assert (out[:, :, 3] == 77).all()


def test_param_validation():
    flt = get_filter("median")
    assert flt.validate_params({}) == {"kernel_size": 3}
    for bad in ({"kernel_size": 99}, {"foo": 1}):
        try:
            flt.validate_params(bad)
        except ValueError:
            continue
        raise AssertionError(f"should reject {bad}")
