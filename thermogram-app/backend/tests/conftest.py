"""Shared pytest fixtures.

Every fixture here is constructed from synthetic data so the suite has no
runtime dependency on real thermogram scans or pre-existing calibration files.
"""

import os
import sys

import cv2
import numpy as np
import pytest

# Make `backend/` importable as the package root for tests.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def blank_image():
    """A plain white 200x300 BGR image."""
    return np.full((200, 300, 3), 255, dtype=np.uint8)


@pytest.fixture
def noisy_image(blank_image):
    """The blank image with Gaussian noise added."""
    rng = np.random.default_rng(0)
    noise = rng.normal(0, 15, blank_image.shape).astype(np.int16)
    out = np.clip(blank_image.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return out


@pytest.fixture
def synthetic_curve_image():
    """A white BGR image with a single pinkish curve drawn across it.

    The curve is a sinusoid centred at y=100 with amplitude 30; the colour
    (180, 80, 210) in BGR lands inside the DEFAULT color profile's red-leaning
    rule, so the segmenter should pick it up.
    """
    img = np.full((200, 600, 3), 245, dtype=np.uint8)
    xs = np.arange(600)
    ys = (100 + 30 * np.sin(xs * 0.02)).astype(int)
    for x, y in zip(xs, ys):
        cv2.circle(img, (x, y), 2, (180, 80, 210), -1)
    return img, xs, ys


@pytest.fixture
def linear_curve_image():
    """A white BGR image with a straight pinkish curve at y=150."""
    img = np.full((300, 500, 3), 245, dtype=np.uint8)
    cv2.line(img, (0, 150), (499, 150), (180, 80, 210), 3)
    return img


@pytest.fixture
def sample_calibration():
    """A minimal calibration dict that mirrors what save_calibration_simple writes."""
    return {
        "template_id": "test-template",
        "calibrated_at": "2026-06-04T00:00:00Z",
        "image_dimensions": {"width": 600, "height": 200},
        "horizontal": {
            "top": {"x": 0, "y": 50},
            "top_temp": 40,
            "spacing": 20.0,
            "rotation_angle": 0.0,
            "line_positions": [50.0, 70.0, 90.0, 110.0, 130.0, 150.0, 170.0, 190.0],
        },
        "vertical": {
            "line1_top": {"x": 100, "y": 50},
            "line1_bottom": {"x": 100, "y": 190},
            "line1_hour": "12:00",
            "center_y": 120.0,
            "curvature": 0.0,
            "spacing": 50.0,
            "line_positions": [100.0, 150.0, 200.0, 250.0, 300.0, 350.0, 400.0, 450.0, 500.0],
        },
        "derived": {
            "top_point": {"x": 100, "y": 50},
            "bottom_point": {"x": 100, "y": 190},
            "curve_center_y": 120.0,
            "curve_coeff_a": 0.0,
            "line_spacing": 50.0,
            "line_positions": [100.0, 150.0, 200.0, 250.0, 300.0, 350.0, 400.0, 450.0, 500.0],
            "horizontal_spacing": 20.0,
            "horizontal_positions": [50.0, 70.0, 90.0, 110.0, 130.0, 150.0, 170.0, 190.0],
            "horizontal_top_temp": 40,
            "rotation_angle": 0.0,
            "reference_hour": 12,
            "reference_minute": 0,
            "reference_temp": 40,
        },
    }
