"""
Validator Module - Stage 6 of the thermogram processing pipeline.

Validates extracted data points and flags potential issues.
"""

import numpy as np
import time
from typing import List, Optional
from datetime import datetime

from models import (
    ValidationResult,
    ValidationIssue,
    DataPoint,
    TimingInfo,
)
from configs import ChartConfig, ValidationConfig


class Validator:
    """
    Validates digitized temperature data.

    Stage 6 of the pipeline:
    1. Out-of-range detection
    2. Sudden jump detection
    3. Gap detection
    4. Low confidence flagging
    5. Overall quality assessment
    """

    def __init__(
        self,
        config: Optional[ChartConfig] = None,
        debug: bool = False
    ):
        """
        Initialize validator.

        Args:
            config: Chart configuration (uses defaults if None)
            debug: Enable debug mode
        """
        self.config = config
        self.validation_config = config.validation if config else ValidationConfig()
        self.debug = debug
        self.debug_data = {}

    def validate(
        self,
        data_points: List[DataPoint],
        expected_interval_minutes: int = 10
    ) -> ValidationResult:
        """
        Validate data points and flag issues.

        Args:
            data_points: List of digitized data points
            expected_interval_minutes: Expected sampling interval

        Returns:
            ValidationResult with issues and quality metrics
        """
        start_time = time.perf_counter()

        try:
            if not data_points:
                return self._create_empty_result(start_time, "No data points to validate")

            cfg = self.validation_config
            issues = []

            # Run validation checks
            out_of_range = self._check_out_of_range(data_points, cfg)
            sudden_jumps = self._check_sudden_jumps(data_points, cfg)
            gaps = self._check_gaps(data_points, expected_interval_minutes, cfg)
            low_confidence = self._check_low_confidence(data_points, cfg)

            issues.extend(out_of_range)
            issues.extend(sudden_jumps)
            issues.extend(gaps)
            issues.extend(low_confidence)

            # Compute metrics
            overall_confidence = self._compute_overall_confidence(data_points, issues)
            data_completeness = self._compute_completeness(
                data_points, expected_interval_minutes
            )
            consistency_score = self._compute_consistency(data_points, sudden_jumps)

            # Determine if review is needed
            needs_review = (
                overall_confidence < cfg.review_required_threshold or
                len(sudden_jumps) > 5 or
                data_completeness < 0.8
            )

            review_reason = ""
            if needs_review:
                reasons = []
                if overall_confidence < cfg.review_required_threshold:
                    reasons.append("low confidence")
                if len(sudden_jumps) > 5:
                    reasons.append("many sudden jumps")
                if data_completeness < 0.8:
                    reasons.append("low completeness")
                review_reason = ", ".join(reasons)

            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000

            return ValidationResult(
                issues=issues,
                out_of_range_count=len(out_of_range),
                sudden_jump_count=len(sudden_jumps),
                gap_count=len(gaps),
                low_confidence_count=len(low_confidence),
                overall_confidence=round(overall_confidence, 3),
                needs_review=needs_review,
                review_reason=review_reason,
                data_completeness=round(data_completeness, 3),
                consistency_score=round(consistency_score, 3),
                success=True,
                message=f"Validation complete. {len(issues)} issue(s) found",
                timing=TimingInfo(
                    stage_name="validate",
                    start_time=start_time,
                    end_time=end_time,
                    duration_ms=duration_ms
                )
            )

        except Exception as e:
            return self._create_empty_result(
                start_time, f"Validation failed: {str(e)}"
            )

    def _check_out_of_range(
        self,
        data_points: List[DataPoint],
        cfg: ValidationConfig
    ) -> List[ValidationIssue]:
        """Check for temperatures outside expected range."""
        issues = []
        calibration_cfg = self.config.calibration if self.config else None

        temp_min = calibration_cfg.temp_min_default if calibration_cfg else -10.0
        temp_max = calibration_cfg.temp_max_default if calibration_cfg else 40.0

        for i, dp in enumerate(data_points):
            if dp.temperature < temp_min - cfg.temp_tolerance:
                issues.append(ValidationIssue(
                    type='out_of_range',
                    index=i,
                    message=f"Temperature {dp.temperature}C below minimum {temp_min}C",
                    severity='warning',
                    suggested_value=temp_min
                ))
            elif dp.temperature > temp_max + cfg.temp_tolerance:
                issues.append(ValidationIssue(
                    type='out_of_range',
                    index=i,
                    message=f"Temperature {dp.temperature}C above maximum {temp_max}C",
                    severity='warning',
                    suggested_value=temp_max
                ))

        return issues

    def _check_sudden_jumps(
        self,
        data_points: List[DataPoint],
        cfg: ValidationConfig
    ) -> List[ValidationIssue]:
        """Check for sudden temperature jumps."""
        issues = []

        if len(data_points) < 2:
            return issues

        for i in range(1, len(data_points)):
            prev = data_points[i - 1]
            curr = data_points[i]

            # Parse datetimes to compute time difference
            try:
                prev_dt = datetime.fromisoformat(prev.datetime)
                curr_dt = datetime.fromisoformat(curr.datetime)
                hours_diff = (curr_dt - prev_dt).total_seconds() / 3600

                if hours_diff <= 0:
                    hours_diff = 1/6  # Default to 10 minutes

                temp_change = abs(curr.temperature - prev.temperature)
                change_per_hour = temp_change / hours_diff

                if change_per_hour > cfg.max_temp_jump:
                    # Suggest interpolated value
                    suggested = (prev.temperature + curr.temperature) / 2

                    issues.append(ValidationIssue(
                        type='sudden_jump',
                        index=i,
                        message=f"Temperature changed {temp_change:.1f}C ({change_per_hour:.1f}C/hr)",
                        severity='warning',
                        suggested_value=round(suggested, 2)
                    ))
            except Exception:
                pass

        return issues

    def _check_gaps(
        self,
        data_points: List[DataPoint],
        expected_interval: int,
        cfg: ValidationConfig
    ) -> List[ValidationIssue]:
        """Check for gaps in data."""
        issues = []

        if len(data_points) < 2:
            return issues

        for i in range(1, len(data_points)):
            prev = data_points[i - 1]
            curr = data_points[i]

            try:
                prev_dt = datetime.fromisoformat(prev.datetime)
                curr_dt = datetime.fromisoformat(curr.datetime)
                minutes_diff = (curr_dt - prev_dt).total_seconds() / 60

                if minutes_diff > cfg.max_gap_minutes:
                    issues.append(ValidationIssue(
                        type='gap',
                        index=i,
                        message=f"Gap of {minutes_diff:.0f} minutes detected",
                        severity='info'
                    ))
            except Exception:
                pass

        return issues

    def _check_low_confidence(
        self,
        data_points: List[DataPoint],
        cfg: ValidationConfig
    ) -> List[ValidationIssue]:
        """Flag points with low confidence."""
        issues = []

        for i, dp in enumerate(data_points):
            if dp.confidence < cfg.low_confidence_threshold:
                issues.append(ValidationIssue(
                    type='low_confidence',
                    index=i,
                    message=f"Low confidence: {dp.confidence:.2f}",
                    severity='info'
                ))

        return issues

    def _compute_overall_confidence(
        self,
        data_points: List[DataPoint],
        issues: List[ValidationIssue]
    ) -> float:
        """Compute overall confidence score."""
        if not data_points:
            return 0.0

        # Base confidence from data points
        avg_confidence = np.mean([dp.confidence for dp in data_points])

        # Penalty for issues
        issue_penalty = min(0.3, len(issues) * 0.02)

        return max(0.0, avg_confidence - issue_penalty)

    def _compute_completeness(
        self,
        data_points: List[DataPoint],
        interval_minutes: int
    ) -> float:
        """Compute data completeness score."""
        if len(data_points) < 2:
            return 0.0

        try:
            first_dt = datetime.fromisoformat(data_points[0].datetime)
            last_dt = datetime.fromisoformat(data_points[-1].datetime)
            total_minutes = (last_dt - first_dt).total_seconds() / 60

            expected_points = int(total_minutes / interval_minutes) + 1
            actual_points = len(data_points)

            return min(1.0, actual_points / expected_points) if expected_points > 0 else 1.0
        except Exception:
            return 1.0

    def _compute_consistency(
        self,
        data_points: List[DataPoint],
        jump_issues: List[ValidationIssue]
    ) -> float:
        """Compute consistency score based on jump frequency."""
        if len(data_points) < 2:
            return 1.0

        # Fewer jumps = higher consistency
        jump_ratio = len(jump_issues) / (len(data_points) - 1)
        return max(0.0, 1.0 - jump_ratio)

    def _create_empty_result(self, start_time: float, message: str) -> ValidationResult:
        """Create an empty/failed result."""
        end_time = time.perf_counter()
        return ValidationResult(
            issues=[],
            overall_confidence=0.0,
            needs_review=True,
            review_reason="validation failed",
            success=False,
            message=message,
            timing=TimingInfo(
                stage_name="validate",
                start_time=start_time,
                end_time=end_time,
                duration_ms=(end_time - start_time) * 1000
            )
        )


def validate_data(
    data_points: List[DataPoint],
    config: Optional[ChartConfig] = None,
    expected_interval_minutes: int = 10
) -> ValidationResult:
    """
    Convenience function to validate data points.

    Args:
        data_points: List of data points
        config: Chart configuration (optional)
        expected_interval_minutes: Expected interval (optional)

    Returns:
        ValidationResult
    """
    validator = Validator(config=config)
    return validator.validate(data_points, expected_interval_minutes)


__all__ = ['Validator', 'validate_data']
