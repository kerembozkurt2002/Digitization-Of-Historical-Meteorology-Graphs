"""Tests for the Dewarper module."""

import numpy as np
import pytest
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.dewarper import Dewarper, dewarp_image
from configs import load_config, ChartConfig
from models import DewarpResult, GridOverlayResult, FlattenedGridResult


class TestDewarper:
    """Test cases for Dewarper class."""

    def test_init_default_config(self):
        """Test initialization with default config."""
        dewarper = Dewarper()
        assert dewarper.config is None
        assert dewarper.dewarp_config is not None
        assert dewarper.grid_config is not None

    def test_init_with_config(self):
        """Test initialization with chart config."""
        config = load_config('daily')
        dewarper = Dewarper(config=config)
        assert dewarper.config == config
        assert dewarper.dewarp_config == config.dewarp

    def test_dewarp_returns_result(self):
        """Test that dewarp returns a DewarpResult."""
        image = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        dewarper = Dewarper()
        result = dewarper.dewarp(image)

        assert isinstance(result, DewarpResult)
        assert result.original_image.shape == image.shape
        assert result.straightened_image.shape == image.shape

    def test_dewarp_with_insufficient_lines(self):
        """Test dewarp with uniform image (no lines)."""
        # Uniform image should have no detectable lines
        image = np.ones((200, 300, 3), dtype=np.uint8) * 128
        dewarper = Dewarper()
        result = dewarper.dewarp(image)

        # Should fail gracefully
        assert isinstance(result, DewarpResult)
        assert not result.success or result.grid_lines_detected <= 3

    def test_dewarp_timing_info(self):
        """Test that timing information is recorded."""
        image = np.random.randint(0, 255, (100, 150, 3), dtype=np.uint8)
        dewarper = Dewarper()
        result = dewarper.dewarp(image)

        assert result.timing is not None
        assert result.timing.stage_name == "dewarp"
        assert result.timing.duration_ms >= 0

    def test_dewarp_debug_mode(self):
        """Test debug mode stores intermediate images."""
        image = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        dewarper = Dewarper(debug=True)
        dewarper.dewarp(image)

        assert 'vertical_mask' in dewarper.debug_images

    def test_create_vertical_mask(self):
        """Test vertical mask creation."""
        image = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        dewarper = Dewarper()
        mask = dewarper._create_vertical_mask(image)

        assert mask.shape == (200, 300)
        assert mask.dtype == np.uint8


class TestHorizontalLineDetection:
    """Test cases for horizontal line detection methods."""

    def test_detect_horizontal_lines(self):
        """Test horizontal line detection."""
        image = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        dewarper = Dewarper()
        lines = dewarper.detect_horizontal_lines(image)

        assert isinstance(lines, list)

    def test_detect_vertical_lines(self):
        """Test vertical line detection."""
        image = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        dewarper = Dewarper()
        polylines = dewarper.detect_vertical_lines(image)

        assert isinstance(polylines, list)

    def test_line_format(self):
        """Test that detected horizontal lines have correct format."""
        # Create image with clear horizontal line
        image = np.ones((200, 300, 3), dtype=np.uint8) * 200
        image[100, :, :] = 0  # Black horizontal line

        dewarper = Dewarper()
        lines = dewarper.detect_horizontal_lines(image)

        # Each line should be [x1, y1, x2, y2]
        for line in lines:
            assert len(line) == 4
            assert line[0] == 0  # x1 starts at left
            assert line[2] == 299  # x2 ends at right


class TestGridOverlay:
    """Test cases for grid overlay methods."""

    def test_create_grid_overlay_original(self):
        """Test grid overlay with mode 0 (original)."""
        image = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        dewarper = Dewarper()
        result = dewarper.create_grid_overlay(image, mode=0)

        assert isinstance(result, GridOverlayResult)
        assert result.success
        assert result.horizontal_lines == 0
        assert np.array_equal(result.overlay_image, image)

    def test_create_grid_overlay_horizontal(self):
        """Test grid overlay with horizontal lines (mode 4)."""
        image = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        dewarper = Dewarper()
        result = dewarper.create_grid_overlay(image, mode=4)

        assert isinstance(result, GridOverlayResult)
        assert result.success
        assert result.overlay_image.shape == image.shape

    def test_create_grid_overlay_vertical(self):
        """Test grid overlay with vertical lines (mode 5)."""
        image = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        dewarper = Dewarper()
        result = dewarper.create_grid_overlay(image, mode=5)

        assert isinstance(result, GridOverlayResult)
        assert result.success
        assert result.overlay_image.shape == image.shape

    def test_create_grid_overlay_combined(self):
        """Test grid overlay with both lines (mode 6)."""
        image = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        dewarper = Dewarper()
        result = dewarper.create_grid_overlay(image, mode=6)

        assert isinstance(result, GridOverlayResult)
        assert result.success
        assert result.overlay_image.shape == image.shape

    def test_create_flattened_grid(self):
        """Test flattened grid creation."""
        image = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        dewarper = Dewarper()
        result = dewarper.create_flattened_grid(image)

        assert isinstance(result, FlattenedGridResult)
        assert result.flattened_image.shape == image.shape

    def test_create_straightened_image(self):
        """Test straightened image creation."""
        image = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        dewarper = Dewarper()
        result = dewarper.create_straightened_image(image)

        assert isinstance(result, FlattenedGridResult)
        assert result.flattened_image.shape == image.shape


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_grayscale_input(self):
        """Test with grayscale input."""
        image = np.random.randint(0, 255, (200, 300), dtype=np.uint8)
        dewarper = Dewarper()
        result = dewarper.dewarp(image)

        assert isinstance(result, DewarpResult)

    def test_small_image(self):
        """Test with small image."""
        image = np.random.randint(0, 255, (50, 75, 3), dtype=np.uint8)
        dewarper = Dewarper()
        result = dewarper.dewarp(image)

        assert isinstance(result, DewarpResult)

    def test_large_image(self):
        """Test with large image."""
        image = np.random.randint(0, 255, (1000, 1500, 3), dtype=np.uint8)
        dewarper = Dewarper()
        result = dewarper.dewarp(image)

        assert isinstance(result, DewarpResult)


class TestGroupAndCreateLines:
    """Test the _group_and_create_lines method."""

    def test_empty_input(self):
        """Test with empty input."""
        dewarper = Dewarper()
        result = dewarper._group_and_create_lines([], 300)

        assert result == []

    def test_single_line(self):
        """Test with single y position."""
        dewarper = Dewarper()
        result = dewarper._group_and_create_lines([100], 300)

        assert len(result) == 1
        assert result[0][1] == 100  # y1
        assert result[0][3] == 100  # y2

    def test_grouped_lines(self):
        """Test that nearby lines are grouped."""
        dewarper = Dewarper()
        # These should be grouped together (within 10 pixels)
        result = dewarper._group_and_create_lines([100, 102, 105, 200], 300)

        assert len(result) == 2  # Two groups


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
