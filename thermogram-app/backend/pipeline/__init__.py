"""
Thermogram Processing Pipeline

A 6-stage pipeline for digitizing historical thermogram charts:

1. Preprocessor - Normalize, denoise, enhance contrast, detect ROI
2. Dewarper - Straighten curved grid lines
3. Calibrator - Map pixels to real-world values (time, temperature)
4. Segmenter - Extract temperature curve from grid
5. Digitizer - Convert curve to data points
6. Validator - Quality assessment and issue detection
"""

# Stage 1: Preprocessor
from .preprocessor import Preprocessor, preprocess_image

# Stage 2: Dewarper
from .dewarper import (
    Dewarper,
    dewarp_image,
)

# Stage 3: Calibrator
from .calibrator import Calibrator, calibrate_image

# Stage 4: Segmenter
from .segmenter import Segmenter, segment_image

# Stage 5: Digitizer
from .digitizer import Digitizer, digitize_curve

# Stage 6: Validator
from .validator import Validator, validate_data

# Re-export result types from models for convenience
from models import (
    PreprocessResult,
    DewarpResult,
    GridOverlayResult,
    FlattenedGridResult,
    CalibrationResult,
    SegmentResult,
    CurveSegment,
    DigitizeResult,
    ValidationResult,
    DataPoint,
    ValidationIssue,
    ProcessingSession,
)


__all__ = [
    # Stage classes
    'Preprocessor',
    'Dewarper',
    'Calibrator',
    'Segmenter',
    'Digitizer',
    'Validator',
    # Convenience functions
    'preprocess_image',
    'dewarp_image',
    'calibrate_image',
    'segment_image',
    'digitize_curve',
    'validate_data',
    # Result types
    'PreprocessResult',
    'DewarpResult',
    'GridOverlayResult',
    'FlattenedGridResult',
    'CalibrationResult',
    'SegmentResult',
    'CurveSegment',
    'DigitizeResult',
    'ValidationResult',
    'DataPoint',
    'ValidationIssue',
    'ProcessingSession',
]
