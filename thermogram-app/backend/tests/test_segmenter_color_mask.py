"""CurveSegmenter._create_color_mask: RGB-rule mask building."""

import numpy as np

from pipeline.color_profiles import DEFAULT_PROFILE
from pipeline.segmenter import CurveSegmenter


def test_mask_shape_and_dtype(linear_curve_image):
    mask = CurveSegmenter()._create_color_mask(linear_curve_image, DEFAULT_PROFILE)
    assert mask.shape == linear_curve_image.shape[:2]
    assert mask.dtype == np.uint8


def test_mask_is_binary(linear_curve_image):
    mask = CurveSegmenter()._create_color_mask(linear_curve_image, DEFAULT_PROFILE)
    assert set(np.unique(mask).tolist()).issubset({0, 255})


def test_mask_highlights_pink_curve(linear_curve_image):
    """The drawn pink line at y=150 should produce a band of non-zero pixels."""
    mask = CurveSegmenter()._create_color_mask(linear_curve_image, DEFAULT_PROFILE)
    near_curve = mask[148:153, :].sum()
    far_from_curve = mask[10:30, :].sum()
    assert near_curve > 0
    assert near_curve > far_from_curve


def test_mask_empty_on_white_canvas():
    """A pure white canvas has no curve pixels, so the mask must be all zero."""
    white = np.full((100, 100, 3), 255, dtype=np.uint8)
    mask = CurveSegmenter()._create_color_mask(white, DEFAULT_PROFILE)
    assert mask.sum() == 0
