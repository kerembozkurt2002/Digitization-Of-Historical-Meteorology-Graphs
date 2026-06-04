"""CalibrationProcessor: save and reload roundtrip via the simple writer."""

import json
from pathlib import Path

import pytest

from pipeline.calibration_processor import CalibrationProcessor, save_calibration_simple


@pytest.fixture
def isolated_processor(tmp_path, monkeypatch):
    """Run save_calibration_simple against a tmp dir instead of the real
    backend/calibrations/."""
    processor = CalibrationProcessor(calibrations_dir=tmp_path)
    monkeypatch.setattr(
        "pipeline.calibration_processor._processor", processor, raising=False
    )
    return processor


def _make_payload(template_id: str) -> dict:
    return {
        "template_id": template_id,
        "horizontal": {
            "top": {"x": 0, "y": 50},
            "end_point": {"x": 600, "y": 50},
            "top_temp": 40,
            "spacing": 20.0,
            "rotation_angle": 0.0,
        },
        "vertical": {
            "line1_top": {"x": 100, "y": 50},
            "line1_bottom": {"x": 100, "y": 190},
            "line1_hour": "12:30",
            "center_y": 120.0,
            "curvature": 0.0005,
            "spacing": 50.0,
        },
        "image_width": 600,
        "image_height": 200,
    }


def test_save_writes_a_json_file(isolated_processor):
    out = save_calibration_simple(_make_payload("test-save"))
    path = Path(isolated_processor._get_calibration_path("test-save"))
    assert path.exists()
    on_disk = json.loads(path.read_text())
    assert on_disk["template_id"] == "test-save"
    assert out["derived"]["line_spacing"] == 50.0


def test_save_parses_reference_hour(isolated_processor):
    out = save_calibration_simple(_make_payload("test-hour"))
    assert out["derived"]["reference_hour"] == 12
    assert out["derived"]["reference_minute"] == 30


def test_save_preserves_curvature_coefficient(isolated_processor):
    out = save_calibration_simple(_make_payload("test-curv"))
    assert out["derived"]["curve_coeff_a"] == pytest.approx(0.0005)
    assert out["derived"]["curve_center_y"] == 120.0


def test_has_calibration_after_save(isolated_processor):
    save_calibration_simple(_make_payload("test-has"))
    assert isolated_processor.has_calibration("test-has") is True
    assert isolated_processor.has_calibration("missing-template") is False
