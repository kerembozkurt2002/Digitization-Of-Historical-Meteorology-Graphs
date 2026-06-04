"""snap_drawing_to_curve: smooth a hand-drawn stroke."""

import numpy as np

from pipeline.segmenter import snap_drawing_to_curve


def test_snap_requires_at_least_two_points():
    result = snap_drawing_to_curve(None, [{"x": 1.0, "y": 1.0}])
    assert result.success is False
    assert result.num_points == 0


def test_snap_interpolates_to_regular_interval():
    drawn = [{"x": 0.0, "y": 100.0}, {"x": 100.0, "y": 100.0}]
    result = snap_drawing_to_curve(None, drawn, sample_interval=10)
    assert result.success
    # Expect roughly (100 / 10) + 1 = 11 samples.
    assert 9 <= result.num_points <= 12
    xs = [p.x for p in result.points]
    assert xs == sorted(xs)


def test_snap_smooths_jittery_input():
    """A line with high-frequency noise should be smoother after snapping."""
    xs_in = np.arange(0, 200, 2, dtype=float)
    rng = np.random.default_rng(42)
    ys_in = 100.0 + rng.normal(0, 5.0, xs_in.shape)
    drawn = [{"x": float(x), "y": float(y)} for x, y in zip(xs_in, ys_in)]
    result = snap_drawing_to_curve(None, drawn, sample_interval=2)
    assert result.success
    ys_out = np.array([p.y for p in result.points])
    assert ys_out.std() < ys_in.std()
