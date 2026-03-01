"""
Configuration system for thermogram processing.

Provides chart-specific parameters for each pipeline stage.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional


@dataclass
class PreprocessConfig:
    """Preprocessing stage configuration."""
    # CLAHE parameters
    clahe_clip_limit: float = 2.0
    clahe_tile_size: int = 8

    # Bilateral filter parameters
    bilateral_d: int = 9
    bilateral_sigma_color: float = 75.0
    bilateral_sigma_space: float = 75.0

    # ROI detection
    roi_margin: float = 0.02  # Margin as fraction of image size


@dataclass
class GridDetectionConfig:
    """Grid detection configuration."""
    # Morphological kernel sizes
    vertical_kernel_height: int = 25
    vertical_kernel_width: int = 1
    horizontal_kernel_height: int = 1
    horizontal_kernel_width: int = 25

    # Hough transform parameters
    hough_threshold: int = 30
    hough_min_line_length_ratio: float = 0.125  # Fraction of image dimension
    hough_max_gap: int = 50

    # Line clustering
    cluster_threshold: int = 10
    min_line_angle_vertical: float = 60.0  # Degrees
    max_line_angle_horizontal: float = 30.0  # Degrees


@dataclass
class DewarpConfig:
    """Dewarping stage configuration."""
    # Sampling parameters
    num_y_samples: int = 50
    min_line_spacing: int = 20

    # Polynomial fitting
    polynomial_degree: int = 2

    # Displacement limits
    max_displacement_ratio: float = 0.1  # Max 10% of image width

    # Smoothing
    gaussian_kernel_size: int = 15


@dataclass
class CalibrationConfig:
    """Calibration stage configuration."""
    # Time axis
    time_axis: str = "x"  # 'x' or 'y'
    hours_per_chart: int = 24

    # Temperature axis
    temp_axis: str = "y"  # 'x' or 'y'
    temp_min: float = -10.0  # Celsius
    temp_max: float = 40.0  # Celsius
    temp_major_gridlines: int = 10  # Number of major gridlines


@dataclass
class SegmentConfig:
    """Segmentation stage configuration."""
    # Curve color detection (HSV ranges)
    curve_hue_min: int = 0
    curve_hue_max: int = 180
    curve_sat_min: int = 0
    curve_sat_max: int = 50
    curve_val_min: int = 0
    curve_val_max: int = 100

    # Morphological operations
    curve_kernel_size: int = 3
    min_curve_length: int = 100


@dataclass
class DigitizeConfig:
    """Digitization stage configuration."""
    # Sampling interval
    sample_interval_minutes: int = 10

    # Interpolation
    interpolation_method: str = "linear"

    # Confidence calculation
    min_confidence: float = 0.5


@dataclass
class ValidationConfig:
    """Validation stage configuration."""
    # Out-of-range detection
    temp_tolerance: float = 5.0  # Degrees outside range to flag

    # Jump detection
    max_temp_jump: float = 10.0  # Max degrees per hour

    # Gap detection
    max_gap_minutes: int = 30

    # Confidence thresholds
    low_confidence_threshold: float = 0.6
    review_required_threshold: float = 0.7


@dataclass
class ChartConfig:
    """Complete configuration for a chart type."""
    name: str
    chart_type: str  # 'daily', 'four_day', 'weekly'
    description: str = ""

    # Stage configurations
    preprocess: PreprocessConfig = field(default_factory=PreprocessConfig)
    grid_detection: GridDetectionConfig = field(default_factory=GridDetectionConfig)
    dewarp: DewarpConfig = field(default_factory=DewarpConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    segment: SegmentConfig = field(default_factory=SegmentConfig)
    digitize: DigitizeConfig = field(default_factory=DigitizeConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)


def _dataclass_to_dict(obj: Any) -> Dict[str, Any]:
    """Convert a dataclass instance to a dictionary."""
    from dataclasses import fields, is_dataclass

    if is_dataclass(obj):
        return {f.name: _dataclass_to_dict(getattr(obj, f.name)) for f in fields(obj)}
    return obj


def _dict_to_dataclass(data: Dict[str, Any], cls: type) -> Any:
    """Convert a dictionary to a dataclass instance."""
    from dataclasses import fields, is_dataclass

    if not is_dataclass(cls):
        return data

    field_types = {f.name: f.type for f in fields(cls)}
    kwargs = {}

    for key, value in data.items():
        if key in field_types:
            field_type = field_types[key]
            # Check if the field type is itself a dataclass
            if hasattr(field_type, '__dataclass_fields__'):
                kwargs[key] = _dict_to_dataclass(value, field_type)
            else:
                kwargs[key] = value

    return cls(**kwargs)


class ConfigManager:
    """Manages loading and caching of chart configurations."""

    _instance: Optional['ConfigManager'] = None
    _configs: Dict[str, ChartConfig] = {}

    def __new__(cls) -> 'ConfigManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_default_configs()
        return cls._instance

    def _load_default_configs(self) -> None:
        """Load default configurations."""
        config_dir = Path(__file__).parent

        for config_file in config_dir.glob("*.json"):
            try:
                config = self._load_config_file(config_file)
                self._configs[config.chart_type] = config
            except Exception as e:
                print(f"Warning: Could not load config {config_file}: {e}")

        # Ensure we have at least a default config
        if not self._configs:
            self._configs['daily'] = ChartConfig(
                name="Default Daily",
                chart_type="daily",
                description="Default daily chart configuration"
            )

    def _load_config_file(self, path: Path) -> ChartConfig:
        """Load a configuration from a JSON file."""
        with open(path) as f:
            data = json.load(f)

        # Build nested dataclass structure
        config = ChartConfig(
            name=data.get('name', path.stem),
            chart_type=data.get('chart_type', 'daily'),
            description=data.get('description', '')
        )

        # Load each stage config
        if 'preprocess' in data:
            config.preprocess = _dict_to_dataclass(data['preprocess'], PreprocessConfig)
        if 'grid_detection' in data:
            config.grid_detection = _dict_to_dataclass(data['grid_detection'], GridDetectionConfig)
        if 'dewarp' in data:
            config.dewarp = _dict_to_dataclass(data['dewarp'], DewarpConfig)
        if 'calibration' in data:
            config.calibration = _dict_to_dataclass(data['calibration'], CalibrationConfig)
        if 'segment' in data:
            config.segment = _dict_to_dataclass(data['segment'], SegmentConfig)
        if 'digitize' in data:
            config.digitize = _dict_to_dataclass(data['digitize'], DigitizeConfig)
        if 'validation' in data:
            config.validation = _dict_to_dataclass(data['validation'], ValidationConfig)

        return config

    def get_config(self, chart_type: str = 'daily') -> ChartConfig:
        """Get configuration for a chart type."""
        if chart_type not in self._configs:
            return self._configs.get('daily', ChartConfig(
                name="Default",
                chart_type="daily"
            ))
        return self._configs[chart_type]

    def list_configs(self) -> list[str]:
        """List available configuration types."""
        return list(self._configs.keys())

    def save_config(self, config: ChartConfig, path: Optional[Path] = None) -> None:
        """Save a configuration to a JSON file."""
        if path is None:
            path = Path(__file__).parent / f"{config.chart_type}.json"

        data = _dataclass_to_dict(config)

        with open(path, 'w') as f:
            json.dump(data, f, indent=2)


def load_config(chart_type: str = 'daily') -> ChartConfig:
    """Convenience function to load a chart configuration."""
    return ConfigManager().get_config(chart_type)


def get_config_manager() -> ConfigManager:
    """Get the singleton ConfigManager instance."""
    return ConfigManager()


__all__ = [
    'PreprocessConfig',
    'GridDetectionConfig',
    'DewarpConfig',
    'CalibrationConfig',
    'SegmentConfig',
    'DigitizeConfig',
    'ValidationConfig',
    'ChartConfig',
    'ConfigManager',
    'load_config',
    'get_config_manager',
]
