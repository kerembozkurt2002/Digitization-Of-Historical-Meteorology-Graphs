"""Tests for the Preprocessor module."""

import numpy as np
import pytest
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.preprocessor import Preprocessor, preprocess_image
from configs import load_config, ChartConfig
from models import PreprocessResult


class TestPreprocessor:
    """Test cases for Preprocessor class."""

    def test_init_default_config(self):
        """Test initialization with default config."""
        preprocessor = Preprocessor()
        assert preprocessor.config is None
        assert preprocessor.preprocess_config is not None

    def test_init_with_config(self):
        """Test initialization with chart config."""
        config = load_config('daily')
        preprocessor = Preprocessor(config=config)
        assert preprocessor.config == config
        assert preprocessor.preprocess_config == config.preprocess

    def test_process_bgr_image(self):
        """Test processing a BGR image."""
        # Create synthetic BGR image
        image = np.random.randint(0, 255, (100, 150, 3), dtype=np.uint8)

        preprocessor = Preprocessor()
        result = preprocessor.process(image)

        assert isinstance(result, PreprocessResult)
        assert result.success
        assert result.processed_image.shape[:2] == (100, 150)
        assert result.grayscale_image.shape == (100, 150)
        assert len(result.processed_image.shape) == 3  # Still BGR

    def test_process_grayscale_image(self):
        """Test processing a grayscale image."""
        # Create synthetic grayscale image
        image = np.random.randint(0, 255, (100, 150), dtype=np.uint8)

        preprocessor = Preprocessor()
        result = preprocessor.process(image)

        assert isinstance(result, PreprocessResult)
        assert result.success
        assert len(result.processed_image.shape) == 3  # Converted to BGR

    def test_process_16bit_image(self):
        """Test processing a 16-bit image."""
        # Create synthetic 16-bit image
        image = np.random.randint(0, 65535, (100, 150, 3), dtype=np.uint16)

        preprocessor = Preprocessor()
        result = preprocessor.process(image)

        assert isinstance(result, PreprocessResult)
        assert result.success
        assert result.processed_image.dtype == np.uint8

    def test_process_rgba_image(self):
        """Test processing an RGBA image."""
        # Create synthetic RGBA image
        image = np.random.randint(0, 255, (100, 150, 4), dtype=np.uint8)

        preprocessor = Preprocessor()
        result = preprocessor.process(image)

        assert isinstance(result, PreprocessResult)
        assert result.success
        assert result.processed_image.shape[2] == 3  # Converted to BGR

    def test_normalization_applied(self):
        """Test that normalization flag is set."""
        image = np.random.randint(0, 255, (100, 150, 3), dtype=np.uint8)

        preprocessor = Preprocessor()
        result = preprocessor.process(image)

        assert result.normalization_applied

    def test_denoising_applied(self):
        """Test that denoising flag is set."""
        image = np.random.randint(0, 255, (100, 150, 3), dtype=np.uint8)

        preprocessor = Preprocessor()
        result = preprocessor.process(image)

        assert result.denoising_applied

    def test_contrast_enhancement_applied(self):
        """Test that contrast enhancement flag is set."""
        image = np.random.randint(0, 255, (100, 150, 3), dtype=np.uint8)

        preprocessor = Preprocessor()
        result = preprocessor.process(image)

        assert result.contrast_enhancement_applied

    def test_timing_info(self):
        """Test that timing information is recorded."""
        image = np.random.randint(0, 255, (100, 150, 3), dtype=np.uint8)

        preprocessor = Preprocessor()
        result = preprocessor.process(image)

        assert result.timing is not None
        assert result.timing.stage_name == "preprocess"
        assert result.timing.duration_ms >= 0

    def test_debug_mode(self):
        """Test debug mode stores intermediate images."""
        image = np.random.randint(0, 255, (100, 150, 3), dtype=np.uint8)

        preprocessor = Preprocessor(debug=True)
        preprocessor.process(image)

        assert 'normalized' in preprocessor.debug_images
        assert 'denoised' in preprocessor.debug_images
        assert 'enhanced' in preprocessor.debug_images

    def test_process_grayscale_method(self):
        """Test the simplified grayscale processing method."""
        image = np.random.randint(0, 255, (100, 150, 3), dtype=np.uint8)

        preprocessor = Preprocessor()
        result = preprocessor.process_grayscale(image)

        assert isinstance(result, np.ndarray)
        assert len(result.shape) == 2  # Grayscale
        assert result.shape == (100, 150)

    def test_crop_to_roi(self):
        """Test ROI cropping."""
        image = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        roi_bounds = (50, 50, 100, 100)

        preprocessor = Preprocessor()
        cropped = preprocessor.crop_to_roi(image, roi_bounds)

        assert cropped.shape == (100, 100, 3)


class TestPreprocessImageFunction:
    """Test cases for preprocess_image convenience function."""

    def test_basic_call(self):
        """Test basic function call."""
        image = np.random.randint(0, 255, (100, 150, 3), dtype=np.uint8)

        result = preprocess_image(image)

        assert isinstance(result, PreprocessResult)
        assert result.success

    def test_with_config(self):
        """Test function call with config."""
        image = np.random.randint(0, 255, (100, 150, 3), dtype=np.uint8)
        config = load_config('daily')

        result = preprocess_image(image, config=config)

        assert isinstance(result, PreprocessResult)
        assert result.success


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_small_image(self):
        """Test processing very small image."""
        image = np.random.randint(0, 255, (10, 10, 3), dtype=np.uint8)

        preprocessor = Preprocessor()
        result = preprocessor.process(image)

        assert result.success

    def test_large_image(self):
        """Test processing large image."""
        image = np.random.randint(0, 255, (2000, 3000, 3), dtype=np.uint8)

        preprocessor = Preprocessor()
        result = preprocessor.process(image)

        assert result.success

    def test_uniform_image(self):
        """Test processing uniform color image."""
        image = np.ones((100, 150, 3), dtype=np.uint8) * 128

        preprocessor = Preprocessor()
        result = preprocessor.process(image)

        assert result.success


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
