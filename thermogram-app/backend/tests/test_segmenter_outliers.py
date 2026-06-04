"""CurveSegmenter._remove_outliers: MAD-based outlier rejection."""

import numpy as np

from pipeline.segmenter import CurveSegmenter


def test_clean_signal_keeps_every_point():
    seg = CurveSegmenter()
    ys = np.full(200, 100.0, dtype=np.float32)
    valid = seg._remove_outliers(ys)
    assert valid.sum() == 200


def test_one_obvious_spike_is_flagged():
    seg = CurveSegmenter()
    ys = np.full(200, 100.0, dtype=np.float32)
    ys[50] = 10.0  # spike well above the MAD threshold
    valid = seg._remove_outliers(ys)
    assert valid[50] is np.bool_(False) or valid[50] == False
    assert valid.sum() == 199


def test_short_input_treated_as_all_invalid():
    """Fewer than 10 valid samples should make outlier removal return the
    valid mask unchanged (essentially a no-op safety branch)."""
    seg = CurveSegmenter()
    ys = np.array([np.nan] * 200, dtype=np.float32)
    ys[:5] = 100.0
    valid = seg._remove_outliers(ys)
    # The five real samples must survive.
    assert valid[:5].sum() == 5
