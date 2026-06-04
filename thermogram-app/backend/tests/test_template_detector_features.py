"""TemplateDetector.extract_features: feature vector shape and stability."""

import numpy as np

from pipeline.template_detector import TemplateDetector


def test_features_return_finite_floats(synthetic_curve_image):
    img, _, _ = synthetic_curve_image
    features = TemplateDetector().extract_features(img)
    assert features.ndim == 1
    assert features.dtype.kind == "f"
    assert np.isfinite(features).all()


def test_features_vector_has_fixed_size(synthetic_curve_image, blank_image):
    """The feature vector size must be deterministic; otherwise the cosine
    similarity in detect() would compare vectors of unequal length."""
    img, _, _ = synthetic_curve_image
    a = TemplateDetector().extract_features(img)
    b = TemplateDetector().extract_features(blank_image)
    assert a.shape == b.shape


def test_features_handle_grayscale_input():
    """Grayscale inputs should be promoted to BGR internally and still
    produce a feature vector."""
    gray = np.full((150, 400), 200, dtype=np.uint8)
    features = TemplateDetector().extract_features(gray)
    assert features.ndim == 1
    assert features.size > 0


def test_features_change_with_input():
    """Two visually different inputs must not yield identical feature vectors."""
    a = TemplateDetector().extract_features(np.full((150, 400, 3), 250, dtype=np.uint8))
    b = TemplateDetector().extract_features(np.full((150, 400, 3), 60, dtype=np.uint8))
    assert not np.allclose(a, b)
