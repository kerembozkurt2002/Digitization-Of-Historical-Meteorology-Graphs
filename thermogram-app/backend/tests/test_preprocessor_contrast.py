"""Preprocessor._enhance_contrast: CLAHE in LAB."""

import numpy as np

from pipeline.preprocessor import Preprocessor


def test_enhance_preserves_shape_and_dtype():
    rng = np.random.default_rng(1)
    img = rng.integers(80, 180, (100, 120, 3), dtype=np.uint8)
    out = Preprocessor()._enhance_contrast(img)
    assert out.shape == img.shape
    assert out.dtype == np.uint8


def test_enhance_widens_dynamic_range():
    """A low-contrast image (values 80..180) should have a wider standard
    deviation after CLAHE."""
    rng = np.random.default_rng(2)
    img = rng.integers(80, 180, (200, 200, 3), dtype=np.uint8)
    before = float(img.std())
    after = float(Preprocessor()._enhance_contrast(img).std())
    assert after > before


def test_enhance_stays_in_valid_range():
    rng = np.random.default_rng(3)
    img = rng.integers(0, 256, (60, 60, 3), dtype=np.uint8)
    out = Preprocessor()._enhance_contrast(img)
    assert out.min() >= 0
    assert out.max() <= 255
