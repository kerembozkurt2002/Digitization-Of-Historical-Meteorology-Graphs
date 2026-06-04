"""Preprocessor._denoise: bilateral filter behaviour."""

import numpy as np

from pipeline.preprocessor import Preprocessor


def test_denoise_preserves_shape_and_dtype(noisy_image):
    out = Preprocessor()._denoise(noisy_image)
    assert out.shape == noisy_image.shape
    assert out.dtype == noisy_image.dtype


def test_denoise_reduces_variance(noisy_image):
    """Bilateral filter on a smooth field with added Gaussian noise should
    bring the per-channel variance down."""
    before = float(noisy_image.var())
    after = float(Preprocessor()._denoise(noisy_image).var())
    assert after < before


def test_denoise_on_flat_image_is_idempotent(blank_image):
    """A constant image should survive denoising untouched."""
    out = Preprocessor()._denoise(blank_image)
    assert np.array_equal(out, blank_image)
