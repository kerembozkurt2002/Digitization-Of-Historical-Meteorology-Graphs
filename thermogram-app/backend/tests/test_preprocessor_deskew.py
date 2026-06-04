"""Preprocessor._deskew: rotation detection from row edges."""

import cv2
import numpy as np

from pipeline.preprocessor import Preprocessor


def _draw_rectangle_chart(angle_deg: float, w: int = 400, h: int = 300) -> np.ndarray:
    """White canvas with a dark rectangle rotated by angle_deg around the
    centre. Used to give _deskew a clearly skewed boundary to detect."""
    img = np.full((h, w, 3), 255, dtype=np.uint8)
    cv2.rectangle(img, (40, 30), (w - 40, h - 30), (60, 60, 60), -1)
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle_deg, 1.0)
    return cv2.warpAffine(img, M, (w, h), borderValue=(255, 255, 255))


def test_deskew_returns_image_and_angle(blank_image):
    out, angle = Preprocessor()._deskew(blank_image)
    assert out.dtype == np.uint8
    assert isinstance(angle, float)


def test_deskew_ignores_tiny_angles():
    """A perfectly axis-aligned chart should return angle 0 and the same shape."""
    img = _draw_rectangle_chart(0.0)
    out, angle = Preprocessor()._deskew(img)
    assert angle == 0.0
    assert out.shape == img.shape


def test_deskew_rejects_extreme_angles():
    """A 45-degree rotation is way outside the [-10, 10] window the deskew
    routine is willing to correct, so it should refuse the correction."""
    img = _draw_rectangle_chart(45.0)
    out, angle = Preprocessor()._deskew(img)
    assert angle == 0.0
    assert out.shape == img.shape
