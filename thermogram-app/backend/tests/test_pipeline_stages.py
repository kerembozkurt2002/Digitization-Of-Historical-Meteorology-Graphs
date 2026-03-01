"""Tests for pipeline stages 3-6: Calibrator, Segmenter, Digitizer, Validator."""

import numpy as np
import pytest
import sys
import os
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.calibrator import Calibrator, calibrate_image
from pipeline.segmenter import Segmenter, segment_image
from pipeline.digitizer import Digitizer, digitize_curve
from pipeline.validator import Validator, validate_data
from configs import load_config
from models import (
    CalibrationResult,
    SegmentResult,
    DigitizeResult,
    ValidationResult,
    CurveSegment,
    DataPoint,
)


# ============================================================================
# Calibrator Tests
# ============================================================================

class TestCalibrator:
    """Test cases for Calibrator class."""

    def test_init_default_config(self):
        """Test initialization with default config."""
        calibrator = Calibrator()
        assert calibrator.config is None
        assert calibrator.calibration_config is not None

    def test_init_with_config(self):
        """Test initialization with chart config."""
        config = load_config('daily')
        calibrator = Calibrator(config=config)
        assert calibrator.config == config

    def test_calibrate_returns_result(self):
        """Test that calibrate returns a CalibrationResult."""
        image = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        calibrator = Calibrator()
        result = calibrator.calibrate(image)

        assert isinstance(result, CalibrationResult)
        assert result.success

    def test_calibrate_coefficients(self):
        """Test that coefficients are computed."""
        image = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        calibrator = Calibrator()
        result = calibrator.calibrate(image)

        assert len(result.time_coefficients) == 2
        assert len(result.temp_coefficients) == 2

    def test_pixel_to_datetime(self):
        """Test pixel to datetime conversion."""
        image = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        calibrator = Calibrator()
        result = calibrator.calibrate(image)

        base_dt = datetime(2024, 1, 1, 0, 0, 0)
        dt = calibrator.pixel_to_datetime(0, result, base_dt)

        assert isinstance(dt, datetime)
        assert dt >= base_dt

    def test_pixel_to_temperature(self):
        """Test pixel to temperature conversion."""
        image = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        calibrator = Calibrator()
        result = calibrator.calibrate(image)

        temp = calibrator.pixel_to_temperature(100, result)
        assert isinstance(temp, float)


class TestCalibrateImageFunction:
    """Test the calibrate_image convenience function."""

    def test_basic_call(self):
        """Test basic function call."""
        image = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        result = calibrate_image(image)

        assert isinstance(result, CalibrationResult)
        assert result.success


# ============================================================================
# Segmenter Tests
# ============================================================================

class TestSegmenter:
    """Test cases for Segmenter class."""

    def test_init_default_config(self):
        """Test initialization with default config."""
        segmenter = Segmenter()
        assert segmenter.config is None
        assert segmenter.segment_config is not None

    def test_segment_returns_result(self):
        """Test that segment returns a SegmentResult."""
        image = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        segmenter = Segmenter()
        result = segmenter.segment(image)

        assert isinstance(result, SegmentResult)

    def test_segment_outputs(self):
        """Test that segment produces expected outputs."""
        image = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        segmenter = Segmenter()
        result = segmenter.segment(image)

        assert result.curve_mask.shape == (200, 300)
        assert result.skeleton_image.shape == (200, 300)

    def test_segment_with_grid_mask(self):
        """Test segmentation with grid mask provided."""
        image = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        grid_mask = np.zeros((200, 300), dtype=np.uint8)
        grid_mask[100, :] = 255  # Horizontal line

        segmenter = Segmenter()
        result = segmenter.segment(image, grid_mask=grid_mask)

        assert isinstance(result, SegmentResult)

    def test_segment_debug_mode(self):
        """Test debug mode stores intermediate images."""
        image = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        segmenter = Segmenter(debug=True)
        segmenter.segment(image)

        assert len(segmenter.debug_images) > 0


class TestSegmentImageFunction:
    """Test the segment_image convenience function."""

    def test_basic_call(self):
        """Test basic function call."""
        image = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        result = segment_image(image)

        assert isinstance(result, SegmentResult)


# ============================================================================
# Digitizer Tests
# ============================================================================

class TestDigitizer:
    """Test cases for Digitizer class."""

    def test_init_default_config(self):
        """Test initialization with default config."""
        digitizer = Digitizer()
        assert digitizer.config is None
        assert digitizer.digitize_config is not None

    def test_digitize_empty_segments(self):
        """Test digitization with no segments."""
        digitizer = Digitizer()

        # Create minimal calibration result
        calibration = CalibrationResult(
            time_coefficients=(0.1, 0.0),
            temp_coefficients=(-0.1, 40.0)
        )

        result = digitizer.digitize([], calibration, 300)

        assert isinstance(result, DigitizeResult)
        assert not result.success
        assert len(result.data_points) == 0

    def test_digitize_with_segments(self):
        """Test digitization with segments."""
        digitizer = Digitizer()

        # Create calibration result
        calibration = CalibrationResult(
            time_coefficients=(0.1, 0.0),
            temp_coefficients=(-0.1, 40.0)
        )

        # Create test segment
        points = [(i, 100) for i in range(0, 300, 10)]
        segment = CurveSegment(
            points=points,
            start_x=0,
            end_x=290,
            confidence=0.9
        )

        result = digitizer.digitize([segment], calibration, 300)

        assert isinstance(result, DigitizeResult)
        assert result.success
        assert len(result.data_points) > 0

    def test_digitize_data_point_format(self):
        """Test that data points have correct format."""
        digitizer = Digitizer()

        calibration = CalibrationResult(
            time_coefficients=(0.1, 0.0),
            temp_coefficients=(-0.1, 40.0)
        )

        points = [(i, 100) for i in range(0, 300, 10)]
        segment = CurveSegment(points=points, start_x=0, end_x=290, confidence=0.9)

        result = digitizer.digitize([segment], calibration, 300)

        if result.data_points:
            dp = result.data_points[0]
            assert isinstance(dp.x_pixel, int)
            assert isinstance(dp.y_pixel, int)
            assert isinstance(dp.datetime, str)
            assert isinstance(dp.temperature, float)
            assert isinstance(dp.confidence, float)


class TestDigitizeCurveFunction:
    """Test the digitize_curve convenience function."""

    def test_basic_call(self):
        """Test basic function call."""
        calibration = CalibrationResult(
            time_coefficients=(0.1, 0.0),
            temp_coefficients=(-0.1, 40.0)
        )

        points = [(i, 100) for i in range(0, 300, 10)]
        segment = CurveSegment(points=points, start_x=0, end_x=290, confidence=0.9)

        result = digitize_curve([segment], calibration, 300)

        assert isinstance(result, DigitizeResult)


# ============================================================================
# Validator Tests
# ============================================================================

class TestValidator:
    """Test cases for Validator class."""

    def test_init_default_config(self):
        """Test initialization with default config."""
        validator = Validator()
        assert validator.config is None
        assert validator.validation_config is not None

    def test_validate_empty_data(self):
        """Test validation with no data."""
        validator = Validator()
        result = validator.validate([])

        assert isinstance(result, ValidationResult)
        assert not result.success

    def test_validate_good_data(self):
        """Test validation with good data."""
        validator = Validator()

        # Create test data points with consistent temperatures
        data_points = []
        for i in range(10):
            dp = DataPoint(
                x_pixel=i * 30,
                y_pixel=100,
                datetime=f"2024-01-01T{i:02d}:00:00",
                temperature=20.0 + i * 0.5,  # Gradual increase
                confidence=0.9
            )
            data_points.append(dp)

        result = validator.validate(data_points)

        assert isinstance(result, ValidationResult)
        assert result.success

    def test_validate_out_of_range(self):
        """Test detection of out-of-range values."""
        config = load_config('daily')
        validator = Validator(config=config)

        # Create data with extreme temperature
        data_points = [
            DataPoint(
                x_pixel=0, y_pixel=100,
                datetime="2024-01-01T00:00:00",
                temperature=100.0,  # Way above normal range
                confidence=0.9
            )
        ]

        result = validator.validate(data_points)

        assert result.out_of_range_count >= 1

    def test_validate_sudden_jump(self):
        """Test detection of sudden jumps."""
        validator = Validator()

        # Create data with sudden temperature jump
        data_points = [
            DataPoint(
                x_pixel=0, y_pixel=100,
                datetime="2024-01-01T00:00:00",
                temperature=20.0,
                confidence=0.9
            ),
            DataPoint(
                x_pixel=30, y_pixel=50,
                datetime="2024-01-01T00:10:00",
                temperature=50.0,  # Jump of 30 degrees in 10 minutes
                confidence=0.9
            )
        ]

        result = validator.validate(data_points)

        assert result.sudden_jump_count >= 1

    def test_validate_low_confidence(self):
        """Test detection of low confidence points."""
        validator = Validator()

        data_points = [
            DataPoint(
                x_pixel=0, y_pixel=100,
                datetime="2024-01-01T00:00:00",
                temperature=20.0,
                confidence=0.3  # Low confidence
            )
        ]

        result = validator.validate(data_points)

        assert result.low_confidence_count >= 1

    def test_overall_confidence(self):
        """Test overall confidence calculation."""
        validator = Validator()

        data_points = [
            DataPoint(
                x_pixel=i * 30, y_pixel=100,
                datetime=f"2024-01-01T{i:02d}:00:00",
                temperature=20.0,
                confidence=0.95
            )
            for i in range(5)
        ]

        result = validator.validate(data_points)

        assert 0.0 <= result.overall_confidence <= 1.0


class TestValidateDataFunction:
    """Test the validate_data convenience function."""

    def test_basic_call(self):
        """Test basic function call."""
        data_points = [
            DataPoint(
                x_pixel=0, y_pixel=100,
                datetime="2024-01-01T00:00:00",
                temperature=20.0,
                confidence=0.9
            )
        ]

        result = validate_data(data_points)

        assert isinstance(result, ValidationResult)


# ============================================================================
# Integration Tests
# ============================================================================

class TestPipelineIntegration:
    """Test integration between pipeline stages."""

    def test_calibrator_to_digitizer(self):
        """Test passing calibration result to digitizer."""
        # Calibrate
        image = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        calibrator = Calibrator()
        cal_result = calibrator.calibrate(image)

        # Digitize with calibration
        points = [(i, 100) for i in range(0, 300, 10)]
        segment = CurveSegment(points=points, start_x=0, end_x=290, confidence=0.9)

        digitizer = Digitizer()
        dig_result = digitizer.digitize([segment], cal_result, 300)

        assert dig_result.success

    def test_digitizer_to_validator(self):
        """Test passing digitizer result to validator."""
        # Create calibration and digitize
        calibration = CalibrationResult(
            time_coefficients=(0.1, 0.0),
            temp_coefficients=(-0.1, 40.0)
        )

        points = [(i, 100) for i in range(0, 300, 10)]
        segment = CurveSegment(points=points, start_x=0, end_x=290, confidence=0.9)

        digitizer = Digitizer()
        dig_result = digitizer.digitize([segment], calibration, 300)

        # Validate
        validator = Validator()
        val_result = validator.validate(dig_result.data_points)

        assert isinstance(val_result, ValidationResult)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
