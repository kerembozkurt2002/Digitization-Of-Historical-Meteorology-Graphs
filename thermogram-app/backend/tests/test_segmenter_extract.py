"""CurveSegmenter.extract: end-to-end on a synthetic curve."""

import numpy as np

from pipeline.segmenter import CurvePoint, CurveSegmenter


def test_extract_recovers_straight_line(linear_curve_image):
    """A horizontal pink line at y=150 must be extracted within a few pixels."""
    result = CurveSegmenter().extract(linear_curve_image, sample_interval=5)
    assert result.success, result.message
    assert result.num_points > 10
    ys = np.array([p.y for p in result.points])
    assert abs(ys.mean() - 150) < 3.0
    assert ys.std() < 3.0


def test_extract_returns_curve_points_in_order(linear_curve_image):
    result = CurveSegmenter().extract(linear_curve_image, sample_interval=5)
    xs = [p.x for p in result.points]
    assert xs == sorted(xs)
    assert all(isinstance(p, CurvePoint) for p in result.points)


def test_extract_fails_clean_on_blank_image(blank_image):
    """A pure white image has nothing to extract; the segmenter must say so
    without raising."""
    result = CurveSegmenter().extract(blank_image, sample_interval=5)
    assert result.success is False
    assert result.num_points == 0


def test_extract_follows_a_sinusoid(synthetic_curve_image):
    img, xs_truth, ys_truth = synthetic_curve_image
    result = CurveSegmenter().extract(img, sample_interval=5)
    assert result.success
    # Match each extracted point against the ground-truth y at its x and
    # require the mean error to stay small.
    errs = [abs(p.y - ys_truth[int(p.x)]) for p in result.points if 0 <= int(p.x) < len(ys_truth)]
    assert np.mean(errs) < 5.0
