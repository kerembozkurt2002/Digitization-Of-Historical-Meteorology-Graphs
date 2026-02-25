"""
Thermogram Processing Pipeline

Stages:
1. Preprocessor - Normalize, denoise, crop
2. Dewarper - Straighten curved grid lines
3. Calibrator - Map pixels to real values
4. Segmenter - Extract curve from grid
5. Digitizer - Convert curve to datapoints
6. Validator - Confidence scoring
"""

from .dewarper import Dewarper, DewarpResult

__all__ = ['Dewarper', 'DewarpResult']
