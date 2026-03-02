"""Data models for thermogram processing pipeline."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
import numpy as np


# ============================================================================
# Core Data Types
# ============================================================================

@dataclass
class DataPoint:
    """A single data point extracted from the thermogram curve."""
    x_pixel: int
    y_pixel: int
    datetime: str  # ISO format
    temperature: float  # Celsius
    confidence: float  # 0.0 - 1.0
    is_edited: bool = False
    is_added: bool = False


@dataclass
class ValidationIssue:
    """A validation issue found in the data."""
    type: str  # 'out_of_range', 'sudden_jump', 'gap', 'low_confidence'
    index: int
    message: str
    severity: str = "warning"  # 'info', 'warning', 'error'
    suggested_value: Optional[float] = None


@dataclass
class ChartMetadata:
    """Metadata for a thermogram chart."""
    filename: str
    filepath: str
    format: str  # 'daily', 'four_day', 'weekly'
    year: Optional[int] = None
    month: Optional[str] = None
    day: Optional[int] = None
    station: Optional[str] = None
    instrument: Optional[str] = None


@dataclass
class CalibrationPoint:
    """A reference point for calibration."""
    x_pixel: int
    y_pixel: int
    datetime: Optional[str] = None  # ISO format
    temperature: Optional[float] = None  # Celsius
    is_reference: bool = True


@dataclass
class TimingInfo:
    """Timing information for a processing stage."""
    stage_name: str
    start_time: float
    end_time: float
    duration_ms: float


# ============================================================================
# Stage 1: Preprocess Result
# ============================================================================

@dataclass
class PreprocessResult:
    """Result of preprocessing stage."""
    # Output images
    original_image: np.ndarray
    processed_image: np.ndarray
    grayscale_image: np.ndarray

    # ROI information
    roi_bounds: Optional[tuple] = None  # (x, y, width, height)
    cropped: bool = False

    # Processing details
    normalization_applied: bool = True
    denoising_applied: bool = True
    contrast_enhancement_applied: bool = True

    # Status
    success: bool = True
    message: str = ""
    timing: Optional[TimingInfo] = None


# ============================================================================
# Stage 2: Dewarp Result
# ============================================================================

@dataclass
class DewarpResult:
    """Result of dewarping operation."""
    original_image: np.ndarray
    straightened_image: np.ndarray
    forward_transform: np.ndarray  # Original -> Straightened
    inverse_transform: np.ndarray  # Straightened -> Original
    grid_lines_detected: int
    success: bool
    message: str
    timing: Optional[TimingInfo] = None

    # Additional metadata
    vertical_lines_count: int = 0
    horizontal_lines_count: int = 0
    displacement_map: Optional[np.ndarray] = None


@dataclass
class GridOverlayResult:
    """Result of grid overlay operation."""
    overlay_image: np.ndarray
    vertical_lines: int
    horizontal_lines: int
    success: bool
    message: str
    # Line positions for client-side rendering
    vertical_line_positions: List[int] = field(default_factory=list)  # X positions at y=0
    horizontal_line_positions: List[int] = field(default_factory=list)  # Y positions
    image_height: int = 0
    image_width: int = 0
    # Curve template coefficients for vertical lines: x = a*y² + b*y + x0
    curve_coeff_a: float = 0.0  # Curvature (how much it bends)
    curve_coeff_b: float = 0.0  # Asymmetry (where the bend is centered)


@dataclass
class FlattenedGridResult:
    """Result of flattened grid operation."""
    flattened_image: np.ndarray
    vertical_lines: int
    horizontal_lines: int
    success: bool
    message: str


# ============================================================================
# Stage 3: Calibration Result
# ============================================================================

@dataclass
class CalibrationResult:
    """Result of calibration stage."""
    # Conversion functions stored as coefficients
    time_coefficients: tuple  # (slope, intercept) for pixel -> minutes
    temp_coefficients: tuple  # (slope, intercept) for pixel -> temperature

    # Reference points used
    reference_points: List[CalibrationPoint] = field(default_factory=list)

    # Detected grid properties
    time_gridlines: List[int] = field(default_factory=list)  # x-pixel positions
    temp_gridlines: List[int] = field(default_factory=list)  # y-pixel positions

    # Time range
    start_datetime: Optional[str] = None
    end_datetime: Optional[str] = None

    # Temperature range
    temp_min: float = -10.0
    temp_max: float = 40.0

    # Confidence
    calibration_confidence: float = 1.0

    # Status
    success: bool = True
    message: str = ""
    timing: Optional[TimingInfo] = None

    def pixel_to_datetime(self, x_pixel: int, base_datetime: Optional[str] = None) -> str:
        """Convert x-pixel to datetime string."""
        slope, intercept = self.time_coefficients
        minutes = slope * x_pixel + intercept
        # This is a placeholder - real implementation would use base_datetime
        hours = int(minutes // 60)
        mins = int(minutes % 60)
        return f"{hours:02d}:{mins:02d}:00"

    def pixel_to_temperature(self, y_pixel: int) -> float:
        """Convert y-pixel to temperature in Celsius."""
        slope, intercept = self.temp_coefficients
        return slope * y_pixel + intercept


# ============================================================================
# Stage 4: Segment Result
# ============================================================================

@dataclass
class CurveSegment:
    """A segment of the detected curve."""
    points: List[tuple]  # [(x, y), ...]
    start_x: int
    end_x: int
    confidence: float = 1.0


@dataclass
class SegmentResult:
    """Result of segmentation stage."""
    # Output images
    curve_mask: np.ndarray  # Binary mask of detected curve
    skeleton_image: np.ndarray  # Skeletonized curve
    grid_removed_image: np.ndarray  # Image with grid removed

    # Detected curve segments
    segments: List[CurveSegment] = field(default_factory=list)

    # Curve properties
    curve_color_hsv: Optional[tuple] = None  # (H, S, V) of curve
    curve_width_avg: float = 1.0

    # Status
    success: bool = True
    message: str = ""
    timing: Optional[TimingInfo] = None


# ============================================================================
# Stage 5: Digitize Result
# ============================================================================

@dataclass
class DigitizeResult:
    """Result of digitization stage."""
    # Extracted data points
    data_points: List[DataPoint] = field(default_factory=list)

    # Raw pixel values before conversion
    raw_points: List[tuple] = field(default_factory=list)  # [(x, y), ...]

    # Sampling info
    sample_interval_minutes: int = 10
    total_samples: int = 0
    interpolated_samples: int = 0

    # Statistics
    temp_min: float = 0.0
    temp_max: float = 0.0
    temp_mean: float = 0.0
    temp_std: float = 0.0

    # Status
    success: bool = True
    message: str = ""
    timing: Optional[TimingInfo] = None


# ============================================================================
# Stage 6: Validation Result
# ============================================================================

@dataclass
class ValidationResult:
    """Result of validation stage."""
    # Validation issues found
    issues: List[ValidationIssue] = field(default_factory=list)

    # Counts by type
    out_of_range_count: int = 0
    sudden_jump_count: int = 0
    gap_count: int = 0
    low_confidence_count: int = 0

    # Overall assessment
    overall_confidence: float = 1.0
    needs_review: bool = False
    review_reason: str = ""

    # Quality metrics
    data_completeness: float = 1.0  # Fraction of expected points present
    consistency_score: float = 1.0  # Based on sudden jumps

    # Status
    success: bool = True
    message: str = ""
    timing: Optional[TimingInfo] = None


# ============================================================================
# Processing Session
# ============================================================================

@dataclass
class ProcessingSession:
    """
    Full pipeline state for a thermogram processing session.
    Tracks all stages and their results.
    """
    # Session info
    session_id: str = ""
    created_at: str = ""
    updated_at: str = ""

    # Input
    metadata: Optional[ChartMetadata] = None
    config_type: str = "daily"

    # Stage results
    preprocess_result: Optional[PreprocessResult] = None
    dewarp_result: Optional[DewarpResult] = None
    calibration_result: Optional[CalibrationResult] = None
    segment_result: Optional[SegmentResult] = None
    digitize_result: Optional[DigitizeResult] = None
    validation_result: Optional[ValidationResult] = None

    # Pipeline state
    current_stage: int = 0  # 0=not started, 1-6=stage number
    completed_stages: List[int] = field(default_factory=list)

    # User edits
    manual_edits: List[Dict[str, Any]] = field(default_factory=list)

    # Overall timing
    total_processing_time_ms: float = 0.0

    @property
    def is_complete(self) -> bool:
        """Check if all stages are complete."""
        return len(self.completed_stages) == 6

    @property
    def final_data_points(self) -> List[DataPoint]:
        """Get final data points (after validation)."""
        if self.digitize_result:
            return self.digitize_result.data_points
        return []

    def get_stage_result(self, stage: int) -> Optional[Any]:
        """Get result for a specific stage."""
        stage_map = {
            1: self.preprocess_result,
            2: self.dewarp_result,
            3: self.calibration_result,
            4: self.segment_result,
            5: self.digitize_result,
            6: self.validation_result,
        }
        return stage_map.get(stage)


# ============================================================================
# Export Types
# ============================================================================

@dataclass
class ExportFormat:
    """Configuration for data export."""
    format: str = "csv"  # 'csv', 'json', 'excel'
    include_metadata: bool = True
    include_confidence: bool = True
    include_validation_flags: bool = True
    datetime_format: str = "%Y-%m-%d %H:%M:%S"
    decimal_places: int = 2


@dataclass
class ExportResult:
    """Result of data export."""
    success: bool
    filepath: str
    format: str
    records_exported: int
    message: str = ""


# ============================================================================
# API Response Types
# ============================================================================

@dataclass
class ProcessingResponse:
    """Standard API response for processing operations."""
    success: bool
    stage: int
    message: str
    data: Optional[Dict[str, Any]] = None
    preview_image: Optional[str] = None  # Base64 encoded
    timing_ms: float = 0.0


@dataclass
class HealthCheckResponse:
    """Health check response."""
    status: str  # 'healthy', 'degraded', 'unhealthy'
    version: str
    stages_available: List[str] = field(default_factory=list)
    message: str = ""


__all__ = [
    # Core types
    'DataPoint',
    'ValidationIssue',
    'ChartMetadata',
    'CalibrationPoint',
    'TimingInfo',
    # Stage results
    'PreprocessResult',
    'DewarpResult',
    'GridOverlayResult',
    'FlattenedGridResult',
    'CalibrationResult',
    'CurveSegment',
    'SegmentResult',
    'DigitizeResult',
    'ValidationResult',
    # Session
    'ProcessingSession',
    # Export
    'ExportFormat',
    'ExportResult',
    # API
    'ProcessingResponse',
    'HealthCheckResponse',
]
