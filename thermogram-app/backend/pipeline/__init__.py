"""
Thermogram Processing Pipeline

Pipeline modules:
1. Preprocessor - Normalize, denoise, enhance contrast
2. Dewarper - Grid line detection for overlay
3. TemplateMatcher - Find "10" labels via template matching
4. TemplateDetector - Detect thermogram template type
5. CalibrationProcessor - Manual grid calibration
"""

# Preprocessor
from .preprocessor import Preprocessor, preprocess_image

# Dewarper (grid detection)
from .dewarper import Dewarper

# Re-export result types from models for convenience
from models import (
    PreprocessResult,
    GridOverlayResult,
)


__all__ = [
    # Stage classes
    'Preprocessor',
    'Dewarper',
    # Convenience functions
    'preprocess_image',
    # Result types
    'PreprocessResult',
    'GridOverlayResult',
]
