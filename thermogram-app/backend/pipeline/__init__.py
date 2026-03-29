"""
Thermogram Processing Pipeline

Pipeline modules:
1. Preprocessor - Normalize, denoise, enhance contrast
2. Dewarper - Grid line detection for overlay
3. TemplateDetector - Detect thermogram template type
4. CalibrationProcessor - Manual grid calibration
5. CurveSegmenter - Extract ink trace curve
"""

# Preprocessor
from .preprocessor import Preprocessor, preprocess_image

# Dewarper (grid detection)
from .dewarper import Dewarper

# Curve segmenter
from .segmenter import CurveSegmenter, extract_curve

# Re-export result types from models for convenience
from models import (
    PreprocessResult,
    GridOverlayResult,
)


__all__ = [
    # Stage classes
    'Preprocessor',
    'Dewarper',
    'CurveSegmenter',
    # Convenience functions
    'preprocess_image',
    'extract_curve',
    # Result types
    'PreprocessResult',
    'GridOverlayResult',
]
