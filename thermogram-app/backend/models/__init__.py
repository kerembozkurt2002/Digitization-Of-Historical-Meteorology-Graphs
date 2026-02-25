"""Data models for thermogram processing."""

from dataclasses import dataclass
from typing import List, Optional


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
    type: str  # 'impossible_value', 'sudden_jump', 'gap'
    index: int
    message: str


@dataclass
class ValidationResult:
    """Result of validation."""
    issues: List[ValidationIssue]
    overall_confidence: float
    needs_review: bool


@dataclass
class ChartMetadata:
    """Metadata for a thermogram chart."""
    filename: str
    filepath: str
    format: str  # 'daily', 'four_day', 'weekly'
    year: Optional[int] = None
    month: Optional[str] = None
    day: Optional[int] = None
