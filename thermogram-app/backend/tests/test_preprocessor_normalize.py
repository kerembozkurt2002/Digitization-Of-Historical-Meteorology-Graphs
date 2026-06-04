"""Preprocessor._normalize: format and bit-depth normalization."""

import numpy as np

from pipeline.preprocessor import Preprocessor


def test_bgr_8bit_passthrough(blank_image):
    out = Preprocessor()._normalize(blank_image)
    assert out.shape == blank_image.shape
    assert out.dtype == np.uint8


def test_grayscale_promoted_to_bgr():
    gray = np.full((50, 60), 128, dtype=np.uint8)
    out = Preprocessor()._normalize(gray)
    assert out.shape == (50, 60, 3)
    assert out.dtype == np.uint8


def test_bgra_stripped_to_bgr():
    bgra = np.full((40, 40, 4), 200, dtype=np.uint8)
    out = Preprocessor()._normalize(bgra)
    assert out.shape == (40, 40, 3)
    assert out.dtype == np.uint8


def test_uint16_downconverted_to_uint8():
    img = np.full((20, 30, 3), 50000, dtype=np.uint16)
    out = Preprocessor()._normalize(img)
    assert out.dtype == np.uint8
    # 50000 / 256 ≈ 195
    assert abs(int(out[0, 0, 0]) - 195) <= 1


def test_float32_rescaled_to_uint8():
    img = np.full((10, 10, 3), 0.5, dtype=np.float32)
    out = Preprocessor()._normalize(img)
    assert out.dtype == np.uint8
    assert abs(int(out[0, 0, 0]) - 127) <= 1
