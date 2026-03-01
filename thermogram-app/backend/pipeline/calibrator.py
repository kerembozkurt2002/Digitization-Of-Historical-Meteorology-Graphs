"""
Calibrator Module - Stage 3 of the thermogram processing pipeline.

Handles pixel-to-value conversions for time and temperature axes.
"""

import numpy as np
import time
from typing import List, Optional, Tuple
from datetime import datetime, timedelta

from models import (
    CalibrationResult,
    CalibrationPoint,
    TimingInfo,
)
from configs import ChartConfig, CalibrationConfig


class Calibrator:
    """
    Calibrates pixel coordinates to real-world values.

    Stage 3 of the pipeline:
    1. Detect time axis gridlines
    2. Detect temperature axis gridlines
    3. Compute pixel-to-datetime conversion
    4. Compute pixel-to-temperature conversion
    """

    def __init__(
        self,
        config: Optional[ChartConfig] = None,
        debug: bool = False
    ):
        """
        Initialize calibrator.

        Args:
            config: Chart configuration (uses defaults if None)
            debug: Enable debug mode
        """
        self.config = config
        self.calibration_config = config.calibration if config else CalibrationConfig()
        self.debug = debug
        self.debug_data = {}

    def calibrate(
        self,
        image: np.ndarray,
        time_gridlines: Optional[List[int]] = None,
        temp_gridlines: Optional[List[int]] = None,
        reference_points: Optional[List[CalibrationPoint]] = None,
        start_datetime: Optional[str] = None,
    ) -> CalibrationResult:
        """
        Perform calibration to map pixels to real values.

        Args:
            image: Processed image (from dewarping stage)
            time_gridlines: X-pixel positions of time gridlines (optional)
            temp_gridlines: Y-pixel positions of temperature gridlines (optional)
            reference_points: Manual reference points (optional)
            start_datetime: Start datetime for the chart (optional)

        Returns:
            CalibrationResult with conversion coefficients
        """
        start_time = time.perf_counter()

        try:
            h, w = image.shape[:2]
            cfg = self.calibration_config

            # Detect or use provided gridlines
            if time_gridlines is None:
                time_gridlines = self._detect_time_gridlines(image)

            if temp_gridlines is None:
                temp_gridlines = self._detect_temp_gridlines(image)

            # Compute time conversion coefficients
            time_coeffs = self._compute_time_coefficients(
                w, time_gridlines, cfg.hours_per_chart
            )

            # Compute temperature conversion coefficients
            temp_coeffs = self._compute_temp_coefficients(
                h, temp_gridlines, cfg.temp_min_default, cfg.temp_max_default
            )

            # Compute confidence based on gridline detection quality
            confidence = self._compute_confidence(
                time_gridlines, temp_gridlines, w, h
            )

            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000

            return CalibrationResult(
                time_coefficients=time_coeffs,
                temp_coefficients=temp_coeffs,
                reference_points=reference_points or [],
                time_gridlines=time_gridlines,
                temp_gridlines=temp_gridlines,
                start_datetime=start_datetime,
                temp_min=cfg.temp_min_default,
                temp_max=cfg.temp_max_default,
                calibration_confidence=confidence,
                success=True,
                message=f"Calibration successful. Time gridlines: {len(time_gridlines)}, Temp gridlines: {len(temp_gridlines)}",
                timing=TimingInfo(
                    stage_name="calibrate",
                    start_time=start_time,
                    end_time=end_time,
                    duration_ms=duration_ms
                )
            )

        except Exception as e:
            end_time = time.perf_counter()
            return CalibrationResult(
                time_coefficients=(0.0, 0.0),
                temp_coefficients=(0.0, 0.0),
                success=False,
                message=f"Calibration failed: {str(e)}",
                timing=TimingInfo(
                    stage_name="calibrate",
                    start_time=start_time,
                    end_time=end_time,
                    duration_ms=(end_time - start_time) * 1000
                )
            )

    def _detect_time_gridlines(self, image: np.ndarray) -> List[int]:
        """
        Detect vertical gridlines for time axis.

        Args:
            image: Input image

        Returns:
            List of x-pixel positions
        """
        h, w = image.shape[:2]
        cfg = self.calibration_config

        # For now, assume evenly spaced gridlines based on chart type
        num_major_lines = cfg.hours_per_chart // 6 + 1  # Major line every 6 hours
        spacing = w / (num_major_lines - 1) if num_major_lines > 1 else w

        gridlines = [int(i * spacing) for i in range(num_major_lines)]

        if self.debug:
            self.debug_data['time_gridlines'] = gridlines

        return gridlines

    def _detect_temp_gridlines(self, image: np.ndarray) -> List[int]:
        """
        Detect horizontal gridlines for temperature axis.

        Args:
            image: Input image

        Returns:
            List of y-pixel positions
        """
        h, w = image.shape[:2]
        cfg = self.calibration_config

        # Assume evenly spaced gridlines
        num_lines = cfg.temp_major_gridlines
        spacing = h / (num_lines - 1) if num_lines > 1 else h

        gridlines = [int(i * spacing) for i in range(num_lines)]

        if self.debug:
            self.debug_data['temp_gridlines'] = gridlines

        return gridlines

    def _compute_time_coefficients(
        self,
        width: int,
        gridlines: List[int],
        hours_per_chart: int
    ) -> Tuple[float, float]:
        """
        Compute pixel-to-minutes conversion coefficients.

        Args:
            width: Image width in pixels
            gridlines: Detected time gridlines
            hours_per_chart: Total hours covered by chart

        Returns:
            (slope, intercept) for minutes = slope * x_pixel + intercept
        """
        total_minutes = hours_per_chart * 60

        # Linear mapping: x=0 -> 0 minutes, x=width -> total_minutes
        slope = total_minutes / width if width > 0 else 0
        intercept = 0.0

        return (slope, intercept)

    def _compute_temp_coefficients(
        self,
        height: int,
        gridlines: List[int],
        temp_min: float,
        temp_max: float
    ) -> Tuple[float, float]:
        """
        Compute pixel-to-temperature conversion coefficients.

        Args:
            height: Image height in pixels
            gridlines: Detected temperature gridlines
            temp_min: Minimum temperature
            temp_max: Maximum temperature

        Returns:
            (slope, intercept) for temp = slope * y_pixel + intercept
        """
        temp_range = temp_max - temp_min

        # Y increases downward, temperature increases upward
        # y=0 -> temp_max, y=height -> temp_min
        slope = -temp_range / height if height > 0 else 0
        intercept = temp_max

        return (slope, intercept)

    def _compute_confidence(
        self,
        time_gridlines: List[int],
        temp_gridlines: List[int],
        width: int,
        height: int
    ) -> float:
        """
        Compute calibration confidence score.

        Args:
            time_gridlines: Detected time gridlines
            temp_gridlines: Detected temperature gridlines
            width: Image width
            height: Image height

        Returns:
            Confidence score (0.0 - 1.0)
        """
        confidence = 1.0

        # Reduce confidence if few gridlines detected
        if len(time_gridlines) < 3:
            confidence *= 0.7
        if len(temp_gridlines) < 3:
            confidence *= 0.7

        return confidence

    def pixel_to_datetime(
        self,
        x_pixel: int,
        result: CalibrationResult,
        base_datetime: Optional[datetime] = None
    ) -> datetime:
        """
        Convert x-pixel to datetime.

        Args:
            x_pixel: X coordinate in pixels
            result: Calibration result with coefficients
            base_datetime: Base datetime (start of chart)

        Returns:
            Datetime at the given pixel
        """
        slope, intercept = result.time_coefficients
        minutes = slope * x_pixel + intercept

        if base_datetime is None:
            base_datetime = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        return base_datetime + timedelta(minutes=minutes)

    def pixel_to_temperature(
        self,
        y_pixel: int,
        result: CalibrationResult
    ) -> float:
        """
        Convert y-pixel to temperature.

        Args:
            y_pixel: Y coordinate in pixels
            result: Calibration result with coefficients

        Returns:
            Temperature in Celsius
        """
        slope, intercept = result.temp_coefficients
        return slope * y_pixel + intercept


def calibrate_image(
    image: np.ndarray,
    config: Optional[ChartConfig] = None,
    **kwargs
) -> CalibrationResult:
    """
    Convenience function to calibrate an image.

    Args:
        image: Input image
        config: Chart configuration (optional)
        **kwargs: Additional arguments for calibrate()

    Returns:
        CalibrationResult
    """
    calibrator = Calibrator(config=config)
    return calibrator.calibrate(image, **kwargs)


__all__ = ['Calibrator', 'calibrate_image']
