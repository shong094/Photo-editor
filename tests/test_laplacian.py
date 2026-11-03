import numpy as np

from backend import filters
from backend.core.registry import get_filter
from backend.core.roi import Rect, apply_filter
from backend.filters.laplacian import KERNELS, laplacian

filters.load_all()


def _impulse(value=50, size=7):
    img = np.zeros((size, size, 3), np.uint8)
    img[size // 2, size // 2] = value
    return img


def _gradient_image():
    rng = np.random.default_rng(0)
    return rng.integers(0, 256, (30, 40, 3), np.uint8)


def test_kernel_response_on_impulse():
    r4 = laplacian(_impulse(), KERNELS["4"])[:, :, 0]
    assert r4[3, 3] == -200
    assert r4[2, 3] == r4[4, 3] == r4[3, 2] == r4[3, 4] == 50
    assert r4[2, 2] == 0

    r8 = laplacian(_impulse(), KERNELS["8"])[:, :, 0]
    assert r8[3, 3] == -400
    assert r8[2, 2] == 50


def test_flat_image_has_no_edges():
    img = np.full((10, 10, 3), 123, np.uint8)
    out = get_filter("laplacian").run(img, neighbors="4", strength=1.0)
    assert (out.views[0][1] == 0).all()
    assert np.array_equal(out.image, img)


def test_sharpen_is_original_minus_laplacian():
    img = _impulse(value=20)
    out = get_filter("laplacian").run(img, neighbors="4", strength=1.0)
    label, edges = out.views[0]
    assert label == "拉普拉斯濾波" and out.result_label == "疊加結果"
    assert edges[3, 3, 0] == 80  # |−4·20|
    assert out.image[3, 3, 0] == 100  # 20 + 80
    assert edges[2, 3, 0] == 20
    assert out.image[2, 3, 0] == 0  # 0 − 20 截斷為 0


def test_strength_zero_keeps_original():
    img = _gradient_image()
    out = get_filter("laplacian").run(img, neighbors="8", strength=0.0)
    assert np.array_equal(out.image, img)


def test_alpha_preserved():
    img = np.dstack([_gradient_image(), np.full((30, 40), 77, np.uint8)])
    out = get_filter("laplacian").run(img, neighbors="4", strength=1.0)
    assert out.image.shape == img.shape
    assert (out.image[:, :, 3] == 77).all()
    assert (out.views[0][1][:, :, 3] == 77).all()


def test_roi_views_are_black_outside_selection():
    img = _gradient_image()
    out = apply_filter(img, get_filter("laplacian"), {"neighbors": "4", "strength": 1.0}, Rect(5, 5, 10, 10))
    edges = out.views[0][1]
    outside = np.ones(img.shape[:2], bool)
    outside[5:15, 5:15] = False
    assert edges.shape == img.shape
    assert (edges[outside] == 0).all()
    assert edges[5:15, 5:15].any()
    assert np.array_equal(out.image[outside], img[outside])
    assert not np.array_equal(out.image[5:15, 5:15], img[5:15, 5:15])


def test_param_validation():
    flt = get_filter("laplacian")
    assert flt.validate_params({}) == {"neighbors": "4", "strength": 1.0}
    for bad in ({"neighbors": "6"}, {"strength": 9}):
        try:
            flt.validate_params(bad)
        except ValueError:
            continue
        raise AssertionError(f"should reject {bad}")
