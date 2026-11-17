import numpy as np

from backend import brushes
from backend.core.brush import _resample, brushes as registry, paint_stroke

brushes.load_all()

WHITE = np.full((40, 60, 3), 255, np.uint8)
RED = (255, 0, 0)


def test_three_brushes_registered():
    assert {b.name for b in registry.all()} == {"hard", "soft", "spray"}


def test_resample_spacing():
    pts = _resample([(0, 0), (10, 0), (10, 10)], 2.5)
    assert pts[0] == (0, 0)
    assert len(pts) == 9  # 總長 20，每 2.5 一點，含起點
    gaps = [np.hypot(x1 - x0, y1 - y0) for (x0, y0), (x1, y1) in zip(pts, pts[1:])]
    assert all(g <= 2.5 + 1e-9 for g in gaps)


def test_hard_line_is_solid_inside_and_untouched_outside():
    out = paint_stroke(WHITE, registry.get("hard"), [(10, 20), (50, 20)], 8, RED)
    assert (out[20, 10:51] == RED).all()       # 線上是純紅
    assert (out[17:24, 15:45] == RED).all()    # 粗細約 8px
    assert (out[0:10] == 255).all()            # 遠處不變
    assert (out[20, 0:5] == 255).all()


def test_single_click_draws_a_dot():
    out = paint_stroke(WHITE, registry.get("hard"), [(30, 20)], 6, RED)
    assert (out[20, 30] == RED).all()
    assert (out[20, 40] == 255).all()


def test_soft_brush_fades_toward_edge():
    out = paint_stroke(WHITE, registry.get("soft"), [(30, 20)], 20, RED)
    g = out[20, 30:41, 1].astype(int)  # 綠色通道：越紅越低
    assert g[0] == 0
    assert all(a <= b for a, b in zip(g, g[1:]))
    assert g[-1] == 255


def test_opacity_blends_with_background():
    out = paint_stroke(WHITE, registry.get("hard"), [(30, 20)], 6, (0, 0, 0), opacity=0.5)
    assert abs(int(out[20, 30, 0]) - 128) <= 1


def test_spray_is_sparse_and_reproducible():
    brush = registry.get("spray")
    a = paint_stroke(WHITE, brush, [(10, 20), (50, 20)], 16, RED, seed=1)
    b = paint_stroke(WHITE, brush, [(10, 20), (50, 20)], 16, RED, seed=1)
    assert np.array_equal(a, b)
    painted = (a[12:29, 10:51] != 255).any(axis=2).mean()
    assert 0.05 < painted < 0.9  # 有噴到但不是實心


def test_paint_on_transparent_becomes_opaque():
    img = np.zeros((20, 20, 4), np.uint8)
    out = paint_stroke(img, registry.get("hard"), [(10, 10)], 6, RED)
    assert tuple(out[10, 10]) == (255, 0, 0, 255)
    assert out[0, 0, 3] == 0


def test_stroke_outside_image_is_ignored():
    out = paint_stroke(WHITE, registry.get("hard"), [(-50, -50), (-40, -40)], 6, RED)
    assert np.array_equal(out, WHITE)


def test_source_stroke_restores_source_pixels():
    painted = paint_stroke(WHITE, registry.get("hard"), [(10, 20), (50, 20)], 10, RED)
    erased = paint_stroke(painted, registry.get("hard"), [(30, 20)], 10, source=WHITE)
    assert (erased[20, 28:33] == 255).all()          # 擦掉的地方回到原圖
    assert (erased[20, 10:20] == RED).all()          # 沒擦到的地方保留


def test_color_and_source_are_exclusive():
    import pytest

    with pytest.raises(ValueError):
        paint_stroke(WHITE, registry.get("hard"), [(1, 1)], 3)
    with pytest.raises(ValueError):
        paint_stroke(WHITE, registry.get("hard"), [(1, 1)], 3, RED, source=WHITE)
    with pytest.raises(ValueError):
        paint_stroke(WHITE, registry.get("hard"), [(1, 1)], 3, source=WHITE[:10])
