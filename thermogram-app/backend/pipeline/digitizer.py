"""
Digitizer Module - Stage 5 of the thermogram processing pipeline.

Converts the extracted curve to data points with timestamps and temperatures.
"""

import numpy as np
import time
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from scipy.signal import savgol_filter

from models import (
    DigitizeResult,
    DataPoint,
    CalibrationResult,
    CurveSegment,
    TimingInfo,
)
from configs import ChartConfig, DigitizeConfig


class Digitizer:
    """
    Digitizes the temperature curve into data points.

    Stage 5 of the pipeline:
    1. Sample curve at regular intervals
    2. Convert pixel coordinates to real values
    3. Calculate confidence per point
    4. Handle gaps and interpolation
    """

    def __init__(
        self,
        config: Optional[ChartConfig] = None,
        debug: bool = False
    ):
        """
        Initialize digitizer.

        Args:
            config: Chart configuration (uses defaults if None)
            debug: Enable debug mode
        """
        self.config = config
        self.digitize_config = config.digitize if config else DigitizeConfig()
        self.debug = debug
        self.debug_data = {}

    def digitize(
        self,
        segments: List[CurveSegment],
        calibration: CalibrationResult,
        image_width: int,
        base_datetime: Optional[datetime] = None
    ) -> DigitizeResult:
        """
        Digitize curve segments into data points.

        Args:
            segments: Curve segments from segmentation
            calibration: Calibration result with conversion coefficients
            image_width: Width of the source image
            base_datetime: Base datetime for the chart

        Returns:
            DigitizeResult with data points
        """
        start_time = time.perf_counter()

        try:
            cfg = self.digitize_config

            if base_datetime is None:
                base_datetime = datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )

            # Combine all points from segments
            all_points = []
            for segment in segments:
                all_points.extend(segment.points)

            if not all_points:
                return self._create_empty_result(start_time, "No curve points found")

            # Create lookup dictionary: x -> list of y values
            x_to_y = {}
            for x, y in all_points:
                if x not in x_to_y:
                    x_to_y[x] = []
                x_to_y[x].append(y)

            # Average y values for each x
            x_to_y_avg = {x: np.mean(ys) for x, ys in x_to_y.items()}

            # Sample at regular intervals
            interval_pixels = self._compute_sample_interval(
                image_width, calibration, cfg.sample_interval_minutes
            )

            data_points = []
            raw_points = []
            interpolated_count = 0

            # Sample from 0 to image_width
            sample_positions = np.arange(0, image_width, interval_pixels)

            # First pass: collect all y values (with interpolation)
            collected_x = []
            collected_y = []
            collected_interpolated = []

            for x_pixel in sample_positions:
                x_int = int(round(x_pixel))

                # Find y value (with interpolation if needed)
                y_pixel, is_interpolated = self._get_y_at_x(
                    x_int, x_to_y_avg, cfg.interpolation_method
                )

                if y_pixel is None:
                    continue

                collected_x.append(x_int)
                collected_y.append(y_pixel)
                collected_interpolated.append(is_interpolated)

            # Apply Savitzky-Golay smoothing if enabled
            if cfg.smoothing_enabled and len(collected_y) > 0:
                y_array = np.array(collected_y)
                smoothed_y = self._apply_smoothing(
                    y_array,
                    cfg.savgol_window_length,
                    cfg.savgol_polyorder
                )
                collected_y = smoothed_y.tolist()

            # Second pass: create data points from (possibly smoothed) y values
            for i, x_int in enumerate(collected_x):
                y_pixel = collected_y[i]
                is_interpolated = collected_interpolated[i]

                if is_interpolated:
                    interpolated_count += 1

                # Convert to real values
                dt = self._pixel_to_datetime(x_int, calibration, base_datetime)
                temp = self._pixel_to_temperature(y_pixel, calibration)

                # Calculate confidence
                confidence = self._calculate_confidence(
                    x_int, y_pixel, x_to_y_avg, segments, is_interpolated
                )

                raw_points.append((x_int, int(y_pixel)))

                data_points.append(DataPoint(
                    x_pixel=x_int,
                    y_pixel=int(y_pixel),
                    datetime=dt.isoformat(),
                    temperature=round(temp, 2),
                    confidence=round(confidence, 3),
                    is_edited=False,
                    is_added=is_interpolated
                ))

            # Compute statistics
            temperatures = [dp.temperature for dp in data_points]
            stats = self._compute_statistics(temperatures)

            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000

            return DigitizeResult(
                data_points=data_points,
                raw_points=raw_points,
                sample_interval_minutes=cfg.sample_interval_minutes,
                total_samples=len(data_points),
                interpolated_samples=interpolated_count,
                temp_min=stats['min'],
                temp_max=stats['max'],
                temp_mean=stats['mean'],
                temp_std=stats['std'],
                success=True,
                message=f"Digitization successful. {len(data_points)} points extracted",
                timing=TimingInfo(
                    stage_name="digitize",
                    start_time=start_time,
                    end_time=end_time,
                    duration_ms=duration_ms
                )
            )

        except Exception as e:
            return self._create_empty_result(start_time, f"Digitization failed: {str(e)}")

    def _compute_sample_interval(
        self,
        image_width: int,
        calibration: CalibrationResult,
        interval_minutes: int
    ) -> float:
        """
        Compute pixel interval for sampling.

        Args:
            image_width: Image width in pixels
            calibration: Calibration result
            interval_minutes: Desired interval in minutes

        Returns:
            Pixel interval
        """
        slope, _ = calibration.time_coefficients
        if slope == 0:
            # Fallback to simple division
            hours_per_chart = 24  # Default
            total_minutes = hours_per_chart * 60
            return image_width * interval_minutes / total_minutes

        # minutes = slope * pixels, so pixels = minutes / slope
        return interval_minutes / slope if slope != 0 else image_width / 144

    def _get_y_at_x(
        self,
        x: int,
        x_to_y: dict,
        method: str
    ) -> Tuple[Optional[float], bool]:
        """
        Get y value at given x, with interpolation if needed.

        Args:
            x: X coordinate
            x_to_y: Dictionary mapping x to average y
            method: Interpolation method

        Returns:
            (y_value, is_interpolated) tuple
        """
        if x in x_to_y:
            return x_to_y[x], False

        # Need to interpolate
        x_values = sorted(x_to_y.keys())
        if not x_values:
            return None, False

        # Find surrounding points
        left_x = None
        right_x = None

        for xv in x_values:
            if xv < x:
                left_x = xv
            elif xv > x and right_x is None:
                right_x = xv
                break

        if method == 'linear':
            if left_x is not None and right_x is not None:
                # Linear interpolation
                t = (x - left_x) / (right_x - left_x)
                y = (1 - t) * x_to_y[left_x] + t * x_to_y[right_x]
                return y, True
            elif left_x is not None:
                return x_to_y[left_x], True
            elif right_x is not None:
                return x_to_y[right_x], True

        return None, False

    def _pixel_to_datetime(
        self,
        x_pixel: int,
        calibration: CalibrationResult,
        base_datetime: datetime
    ) -> datetime:
        """Convert x-pixel to datetime."""
        slope, intercept = calibration.time_coefficients
        minutes = slope * x_pixel + intercept
        return base_datetime + timedelta(minutes=minutes)

    def _pixel_to_temperature(
        self,
        y_pixel: float,
        calibration: CalibrationResult
    ) -> float:
        """Convert y-pixel to temperature."""
        slope, intercept = calibration.temp_coefficients
        return slope * y_pixel + intercept

    def _calculate_confidence(
        self,
        x: int,
        y: float,
        x_to_y: dict,
        segments: List[CurveSegment],
        is_interpolated: bool
    ) -> float:
        """
        Calculate confidence score for a data point.

        Args:
            x: X coordinate
            y: Y coordinate
            x_to_y: X to Y mapping
            segments: Original curve segments
            is_interpolated: Whether point was interpolated

        Returns:
            Confidence score (0.0 - 1.0)
        """
        cfg = self.digitize_config
        confidence = 1.0

        # Reduce confidence for interpolated points
        if is_interpolated:
            confidence *= 0.7

        # Check if point is within a high-confidence segment
        in_segment = False
        for segment in segments:
            if segment.start_x <= x <= segment.end_x:
                in_segment = True
                confidence *= segment.confidence
                break

        if not in_segment:
            confidence *= 0.5

        # Apply minimum threshold
        return max(cfg.min_confidence, min(1.0, confidence))

    def _compute_statistics(self, temperatures: List[float]) -> dict:
        """Compute temperature statistics."""
        if not temperatures:
            return {'min': 0.0, 'max': 0.0, 'mean': 0.0, 'std': 0.0}

        return {
            'min': round(min(temperatures), 2),
            'max': round(max(temperatures), 2),
            'mean': round(np.mean(temperatures), 2),
            'std': round(np.std(temperatures), 2)
        }

    def _apply_smoothing(
        self,
        y_values: np.ndarray,
        window_length: int,
        polyorder: int
    ) -> np.ndarray:
        """
        Apply Savitzky-Golay smoothing to y values.

        Args:
            y_values: Array of y values (may contain NaN)
            window_length: Filter window length (must be odd)
            polyorder: Polynomial order

        Returns:
            Smoothed y values
        """
        # Handle edge cases
        if len(y_values) < window_length:
            # Not enough data points, return original
            return y_values

        # Ensure window_length is odd
        if window_length % 2 == 0:
            window_length += 1

        # Ensure polyorder is less than window_length
        if polyorder >= window_length:
            polyorder = window_length - 1

        # Handle NaN values by interpolating first
        valid_mask = ~np.isnan(y_values)
        if not np.any(valid_mask):
            return y_values

        # Interpolate to fill NaN gaps
        x_all = np.arange(len(y_values))
        x_valid = x_all[valid_mask]
        y_valid = y_values[valid_mask]

        if len(y_valid) < window_length:
            return y_values

        # Interpolate missing values
        y_interpolated = np.interp(x_all, x_valid, y_valid)

        # Apply Savitzky-Golay filter
        try:
            y_smoothed = savgol_filter(y_interpolated, window_length, polyorder)
        except ValueError:
            # If filter fails, return interpolated values
            return y_interpolated

        return y_smoothed

    def _create_empty_result(self, start_time: float, message: str) -> DigitizeResult:
        """Create an empty/failed result."""
        end_time = time.perf_counter()
        return DigitizeResult(
            data_points=[],
            raw_points=[],
            success=False,
            message=message,
            timing=TimingInfo(
                stage_name="digitize",
                start_time=start_time,
                end_time=end_time,
                duration_ms=(end_time - start_time) * 1000
            )
        )


def digitize_curve(
    segments: List[CurveSegment],
    calibration: CalibrationResult,
    image_width: int,
    config: Optional[ChartConfig] = None,
    base_datetime: Optional[datetime] = None
) -> DigitizeResult:
    """
    Convenience function to digitize a curve.

    Args:
        segments: Curve segments
        calibration: Calibration result
        image_width: Image width
        config: Chart configuration (optional)
        base_datetime: Base datetime (optional)

    Returns:
        DigitizeResult
    """
    digitizer = Digitizer(config=config)
    return digitizer.digitize(segments, calibration, image_width, base_datetime)


__all__ = ['Digitizer', 'digitize_curve']
