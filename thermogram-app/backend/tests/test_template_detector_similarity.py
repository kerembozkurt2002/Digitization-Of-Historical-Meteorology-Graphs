"""TemplateDetector.compute_similarity: bounded weighted similarity."""

import numpy as np
import pytest

from pipeline.template_detector import TemplateDetector


@pytest.fixture
def detector():
    return TemplateDetector()


def test_identical_vectors_score_near_one(detector):
    v = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    assert detector.compute_similarity(v, v) == pytest.approx(1.0, abs=1e-6)


def test_zero_vector_yields_zero(detector):
    v = np.zeros(5)
    other = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    assert detector.compute_similarity(v, other) == 0.0
    assert detector.compute_similarity(other, v) == 0.0


def test_similarity_is_in_unit_interval(detector):
    rng = np.random.default_rng(0)
    for _ in range(20):
        a = rng.standard_normal(50)
        b = rng.standard_normal(50)
        s = detector.compute_similarity(a, b)
        assert 0.0 <= s <= 1.0


def test_similar_vectors_score_higher_than_different(detector):
    a = np.array([1.0, 1.0, 1.0, 1.0])
    near = np.array([1.0, 1.0, 1.0, 1.1])
    far = np.array([-1.0, -1.0, -1.0, -1.0])
    assert detector.compute_similarity(a, near) > detector.compute_similarity(a, far)
