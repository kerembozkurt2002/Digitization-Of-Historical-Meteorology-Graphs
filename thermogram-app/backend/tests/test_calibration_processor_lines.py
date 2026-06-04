"""CalibrationProcessor: line position generation and spacing estimation."""

import pytest

from pipeline.calibration_processor import CalibrationProcessor


@pytest.fixture
def processor():
    return CalibrationProcessor()


def test_estimate_spacing_for_daily(processor):
    spacing = processor._estimate_line_spacing("gunluk-1", image_width=2400)
    assert spacing == pytest.approx(2400 / 24)


def test_estimate_spacing_for_four_day(processor):
    spacing = processor._estimate_line_spacing("4_gunluk-1", image_width=9600)
    assert spacing == pytest.approx(9600 / 96)


def test_estimate_spacing_for_weekly(processor):
    spacing = processor._estimate_line_spacing("haftalik-1", image_width=16800)
    assert spacing == pytest.approx(16800 / 168)


def test_estimate_spacing_unknown_template_defaults_to_daily(processor):
    spacing = processor._estimate_line_spacing("unknown-template", image_width=2400)
    assert spacing == pytest.approx(2400 / 24)


def test_generated_lines_are_sorted_and_in_bounds(processor):
    positions = processor._generate_line_positions(reference_x=500.0, spacing=100.0, image_width=1000)
    assert positions == sorted(positions)
    assert all(0 <= p <= 1000 for p in positions)
    # Reference position must be one of the generated lines.
    assert 500.0 in positions


def test_generated_lines_have_expected_count(processor):
    positions = processor._generate_line_positions(reference_x=0.0, spacing=200.0, image_width=1000)
    # x=0,200,400,600,800,1000 → 6 positions if endpoint reached.
    assert len(positions) >= 5
