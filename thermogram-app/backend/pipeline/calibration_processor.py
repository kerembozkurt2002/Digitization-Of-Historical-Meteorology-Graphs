"""
Calibration Processor Module

New 2-point + sliders calibration system:
- User marks TOP and BOTTOM of a single vertical line
- User adjusts centerY (bend center) and curvature sliders
- System calculates line positions across the entire image

Curve formula: x = linearX + curvature * (y - centerY)²
"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class Point:
    """A 2D point."""
    x: float
    y: float


@dataclass
class DerivedCalibration:
    """Calculated values from calibration."""
    # Original calibration inputs
    top_point: Point
    bottom_point: Point
    curve_center_y: float
    curve_coeff_a: float  # curvature coefficient

    # Calculated values
    line_slope: float  # Linear slope of the reference line
    line_mid_x: float  # X at midpoint
    line_mid_y: float  # Y at midpoint
    line_spacing: float  # Distance between grid lines (from auto-detect)
    line_positions: List[float]  # All vertical line x positions


@dataclass
class CalibrationData:
    """Complete calibration data for a template."""
    template_id: str
    calibrated_at: str
    image_dimensions: Dict[str, int]
    derived: DerivedCalibration


class CalibrationProcessor:
    """Processes and stores vertical grid calibration data."""

    def __init__(self, calibrations_dir: Optional[Path] = None):
        if calibrations_dir is None:
            calibrations_dir = Path(__file__).parent.parent / "calibrations"
        self.calibrations_dir = calibrations_dir
        self.calibrations_dir.mkdir(parents=True, exist_ok=True)

    def _get_calibration_path(self, template_id: str) -> Path:
        """Get path to calibration file for a template."""
        return self.calibrations_dir / f"{template_id}.json"

    def has_calibration(self, template_id: str) -> bool:
        """Check if calibration exists for a template."""
        return self._get_calibration_path(template_id).exists()

    def load_calibration(self, template_id: str) -> Optional[CalibrationData]:
        """Load calibration data for a template."""
        path = self._get_calibration_path(template_id)
        if not path.exists():
            return None

        with open(path, 'r') as f:
            data = json.load(f)

        # Handle new format
        derived_data = data['derived']
        top_point = Point(**derived_data['top_point'])
        bottom_point = Point(**derived_data['bottom_point'])

        derived = DerivedCalibration(
            top_point=top_point,
            bottom_point=bottom_point,
            curve_center_y=derived_data['curve_center_y'],
            curve_coeff_a=derived_data['curve_coeff_a'],
            line_slope=derived_data['line_slope'],
            line_mid_x=derived_data['line_mid_x'],
            line_mid_y=derived_data['line_mid_y'],
            line_spacing=derived_data['line_spacing'],
            line_positions=derived_data['line_positions']
        )

        return CalibrationData(
            template_id=data['template_id'],
            calibrated_at=data['calibrated_at'],
            image_dimensions=data['image_dimensions'],
            derived=derived
        )

    def save_calibration(
        self,
        template_id: str,
        top_point: Dict,
        bottom_point: Dict,
        center_y: float,
        curvature: float,
        image_width: int,
        image_height: int,
        line_spacing: Optional[float] = None
    ) -> CalibrationData:
        """
        Save calibration data for a template.

        Args:
            template_id: Template identifier
            top_point: {x, y} - Top of the calibration line
            bottom_point: {x, y} - Bottom of the calibration line
            center_y: Y-coordinate where curve bends
            curvature: Quadratic coefficient (curve_coeff_a)
            image_width: Image width in pixels
            image_height: Image height in pixels
            line_spacing: Optional line spacing (if None, estimate from template type)
        """
        top = Point(x=float(top_point['x']), y=float(top_point['y']))
        bottom = Point(x=float(bottom_point['x']), y=float(bottom_point['y']))

        # Calculate line parameters
        line_slope = (bottom.x - top.x) / (bottom.y - top.y) if bottom.y != top.y else 0
        line_mid_x = (top.x + bottom.x) / 2
        line_mid_y = (top.y + bottom.y) / 2

        # Estimate line spacing if not provided
        if line_spacing is None:
            line_spacing = self._estimate_line_spacing(template_id, image_width)

        # Generate line positions
        line_positions = self._generate_line_positions(
            line_mid_x, line_spacing, image_width
        )

        derived = DerivedCalibration(
            top_point=top,
            bottom_point=bottom,
            curve_center_y=float(center_y),
            curve_coeff_a=float(curvature),
            line_slope=line_slope,
            line_mid_x=line_mid_x,
            line_mid_y=line_mid_y,
            line_spacing=line_spacing,
            line_positions=line_positions
        )

        calibration = CalibrationData(
            template_id=template_id,
            calibrated_at=datetime.utcnow().isoformat() + "Z",
            image_dimensions={"width": image_width, "height": image_height},
            derived=derived
        )

        # Save to file
        path = self._get_calibration_path(template_id)
        with open(path, 'w') as f:
            json.dump(self._to_dict(calibration), f, indent=2)

        return calibration

    def _estimate_line_spacing(self, template_id: str, image_width: int) -> float:
        """Estimate line spacing based on template type."""
        # Template naming convention: gunluk-X, haftalik-X, 4_gunluk-X
        if 'gunluk' in template_id and '4_gunluk' not in template_id:
            # Daily: ~24 lines for 24 hours
            return image_width / 24
        elif '4_gunluk' in template_id:
            # 4-day: ~96 lines (24 * 4)
            return image_width / 96
        elif 'haftalik' in template_id:
            # Weekly: ~168 lines (24 * 7)
            return image_width / 168
        else:
            # Default: assume daily
            return image_width / 24

    def _generate_line_positions(
        self,
        reference_x: float,
        spacing: float,
        image_width: int
    ) -> List[float]:
        """Generate all line positions across the image."""
        positions = []

        # Lines to the left of reference
        x = reference_x
        while x >= 0:
            positions.append(x)
            x -= spacing

        # Lines to the right of reference
        x = reference_x + spacing
        while x <= image_width:
            positions.append(x)
            x += spacing

        return sorted(positions)

    def _to_dict(self, calibration: CalibrationData) -> dict:
        """Convert CalibrationData to dictionary for JSON serialization."""
        return {
            "template_id": calibration.template_id,
            "calibrated_at": calibration.calibrated_at,
            "image_dimensions": calibration.image_dimensions,
            "derived": {
                "top_point": asdict(calibration.derived.top_point),
                "bottom_point": asdict(calibration.derived.bottom_point),
                "curve_center_y": calibration.derived.curve_center_y,
                "curve_coeff_a": calibration.derived.curve_coeff_a,
                "line_slope": calibration.derived.line_slope,
                "line_mid_x": calibration.derived.line_mid_x,
                "line_mid_y": calibration.derived.line_mid_y,
                "line_spacing": calibration.derived.line_spacing,
                "line_positions": calibration.derived.line_positions
            }
        }

    def get_curve_x(
        self,
        calibration: CalibrationData,
        base_x: float,
        y: float
    ) -> float:
        """
        Calculate x position on the curve at given y.

        Formula: x = linearX + curvature * (y - centerY)²
        """
        d = calibration.derived
        # Linear component
        linear_x = base_x + d.line_slope * (y - d.line_mid_y)
        # Quadratic component
        dy = y - d.curve_center_y
        curve_offset = d.curve_coeff_a * dy * dy
        return linear_x + curve_offset


# Module-level functions for easy access
_processor = None


def get_processor() -> CalibrationProcessor:
    """Get or create the calibration processor singleton."""
    global _processor
    if _processor is None:
        _processor = CalibrationProcessor()
    return _processor


def save_calibration(
    template_id: str,
    top_point: Dict,
    bottom_point: Dict,
    center_y: float,
    curvature: float,
    image_width: int,
    image_height: int
) -> CalibrationData:
    """Save calibration data for a template."""
    return get_processor().save_calibration(
        template_id, top_point, bottom_point,
        center_y, curvature, image_width, image_height
    )


def load_calibration(template_id: str) -> Optional[CalibrationData]:
    """Load calibration data for a template."""
    return get_processor().load_calibration(template_id)


def has_calibration(template_id: str) -> bool:
    """Check if calibration exists for a template."""
    return get_processor().has_calibration(template_id)


def save_calibration_full(data: Dict) -> Dict:
    """
    Save comprehensive calibration data (vertical + horizontal).

    Args:
        data: {
            template_id: str,
            vertical: {
                line1_top: {x, y},
                line1_bottom: {x, y},
                line1_hour: str (e.g., "7:30"),
                line2_top: {x, y},
                line2_hour: str,
                last_top: {x, y},
                center_y: float,
                curvature: float
            },
            horizontal: {
                top: {x, y},
                top_temp: int (e.g., 40),
                second: {x, y},
                bottom: {x, y}
            },
            image_width: int,
            image_height: int
        }

    Returns:
        Saved calibration data with computed values.
    """
    template_id = data['template_id']
    vertical = data['vertical']
    horizontal = data['horizontal']
    image_width = data['image_width']
    image_height = data['image_height']

    # Get spacing adjustments (default to 1.0 if not provided)
    v_spacing_adjust = vertical.get('spacing_adjust', 1.0)
    h_spacing_adjust = horizontal.get('spacing_adjust', 1.0)

    # Calculate vertical spacing using first-last method to avoid error accumulation
    v1_x = vertical['line1_top']['x']
    v2_x = vertical['line2_top']['x']
    v_last_x = vertical['last_top']['x']

    # Local spacing estimate (between consecutive lines)
    local_v_spacing = abs(v2_x - v1_x)

    if local_v_spacing < 1:
        local_v_spacing = 50  # Fallback

    # Total span from first to last line
    v_total_span = abs(v_last_x - v1_x)

    # Estimate number of intervals (round to nearest integer)
    num_v_intervals = round(v_total_span / local_v_spacing) if local_v_spacing > 0 else 1

    # Corrected spacing: distribute error evenly across all lines
    base_v_spacing = v_total_span / num_v_intervals if num_v_intervals > 0 else local_v_spacing

    # Apply user adjustment
    v_spacing = base_v_spacing * v_spacing_adjust

    # Calculate horizontal spacing using first-last method
    h_top_y = horizontal['top']['y']
    h_second_y = horizontal['second']['y']
    h_bottom_y = horizontal['bottom']['y']

    # Local spacing estimate (between consecutive lines)
    local_h_spacing = abs(h_second_y - h_top_y)

    if local_h_spacing < 1:
        local_h_spacing = 20  # Fallback

    # Total span from top to bottom line
    h_total_span = abs(h_bottom_y - h_top_y)

    # Estimate number of intervals
    num_h_intervals = round(h_total_span / local_h_spacing) if local_h_spacing > 0 else 1

    # Corrected spacing: distribute error evenly
    base_h_spacing = h_total_span / num_h_intervals if num_h_intervals > 0 else local_h_spacing

    # Apply user adjustment
    h_spacing = base_h_spacing * h_spacing_adjust

    # Generate vertical line positions
    # NOTE: No lines to the LEFT of the first vertical line
    vertical_positions = []

    # Lines from first line to right only
    x = v1_x
    while x <= image_width + v_spacing:
        if 0 <= x <= image_width:
            vertical_positions.append(x)
        x += v_spacing

    vertical_positions = sorted(vertical_positions)

    # Generate horizontal line positions
    # NOTE: No lines ABOVE the first horizontal line
    horizontal_positions = []
    y = h_top_y
    while y <= image_height + h_spacing:
        if 0 <= y <= image_height:
            horizontal_positions.append(y)
        y += h_spacing

    # Build calibration object
    calibration = {
        "template_id": template_id,
        "calibrated_at": datetime.utcnow().isoformat() + "Z",
        "image_dimensions": {
            "width": image_width,
            "height": image_height
        },
        "vertical": {
            "line1_top": vertical['line1_top'],
            "line1_bottom": vertical['line1_bottom'],
            "line1_hour": vertical['line1_hour'],
            "line2_top": vertical['line2_top'],
            "line2_hour": vertical['line2_hour'],
            "last_top": vertical['last_top'],
            "center_y": vertical['center_y'],
            "curvature": vertical['curvature'],
            "spacing": v_spacing,
            "line_positions": vertical_positions,
            "total_lines": len(vertical_positions)
        },
        "horizontal": {
            "top": horizontal['top'],
            "top_temp": horizontal['top_temp'],
            "second": horizontal['second'],
            "bottom": horizontal['bottom'],
            "spacing": h_spacing,
            "line_positions": horizontal_positions,
            "total_lines": len(horizontal_positions)
        },
        # All derived data for frontend rendering
        "derived": {
            "top_point": vertical['line1_top'],
            "bottom_point": vertical['line1_bottom'],
            "curve_center_y": vertical['center_y'],
            "curve_coeff_a": vertical['curvature'],
            "line_spacing": v_spacing,
            "line_positions": vertical_positions,
            # Horizontal data
            "horizontal_spacing": h_spacing,
            "horizontal_positions": horizontal_positions,
            "horizontal_top_temp": horizontal['top_temp']
        }
    }

    # Save to file
    processor = get_processor()
    path = processor._get_calibration_path(template_id)
    with open(path, 'w') as f:
        json.dump(calibration, f, indent=2)

    return calibration


def save_calibration_simple(data: Dict) -> Dict:
    """
    Save simplified calibration data (7-step system with rotation and spacing).

    Args:
        data: {
            template_id: str,
            horizontal: {
                top: {x, y},
                end_point: {x, y},  # For rotation calculation
                top_temp: int (e.g., 40),
                spacing: float (pixels),
                rotation_angle: float (radians)
            },
            vertical: {
                line1_top: {x, y},
                line1_bottom: {x, y},
                line1_hour: str (e.g., "07:30"),
                center_y: float,
                curvature: float,
                spacing: float (pixels)
            },
            image_width: int,
            image_height: int
        }

    Returns:
        Saved calibration data with computed values.
    """
    template_id = data['template_id']
    vertical = data['vertical']
    horizontal = data['horizontal']
    image_width = data['image_width']
    image_height = data['image_height']

    # Get spacing values directly (already in pixels)
    v_spacing = vertical['spacing']
    h_spacing = horizontal['spacing']
    rotation_angle = horizontal.get('rotation_angle', 0.0)

    # Reference point for vertical lines
    v1_x = vertical['line1_top']['x']
    h_top_y = horizontal['top']['y']

    # Parse hour from time string (e.g., "12:30" -> hour=12, minute=30)
    time_str = vertical['line1_hour']
    hour, minute = 12, 0
    if ':' in time_str:
        parts = time_str.split(':')
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0

    # Generate vertical line positions
    # NOTE: No lines to the LEFT of the first vertical line
    vertical_positions = []
    x = v1_x
    while x <= image_width + v_spacing:
        if 0 <= x <= image_width:
            vertical_positions.append(x)
        x += v_spacing

    vertical_positions = sorted(vertical_positions)

    # Generate horizontal line positions
    # NOTE: No lines ABOVE the first horizontal line
    horizontal_positions = []
    y = h_top_y
    while y <= image_height + h_spacing:
        if 0 <= y <= image_height:
            horizontal_positions.append(y)
        y += h_spacing

    horizontal_positions = sorted(horizontal_positions)

    # Build calibration object
    calibration = {
        "template_id": template_id,
        "calibrated_at": datetime.utcnow().isoformat() + "Z",
        "image_dimensions": {
            "width": image_width,
            "height": image_height
        },
        "horizontal": {
            "top": horizontal['top'],
            "end_point": horizontal.get('end_point'),
            "top_temp": horizontal['top_temp'],
            "spacing": h_spacing,
            "rotation_angle": rotation_angle,
            "line_positions": horizontal_positions,
            "total_lines": len(horizontal_positions)
        },
        "vertical": {
            "line1_top": vertical['line1_top'],
            "line1_bottom": vertical['line1_bottom'],
            "line1_hour": vertical['line1_hour'],
            "center_y": vertical['center_y'],
            "curvature": vertical['curvature'],
            "spacing": v_spacing,
            "line_positions": vertical_positions,
            "total_lines": len(vertical_positions)
        },
        # Derived data for frontend rendering and alignment mode
        "derived": {
            "top_point": vertical['line1_top'],
            "bottom_point": vertical['line1_bottom'],
            "curve_center_y": vertical['center_y'],
            "curve_coeff_a": vertical['curvature'],
            "line_spacing": v_spacing,
            "line_positions": vertical_positions,
            # Horizontal data
            "horizontal_spacing": h_spacing,
            "horizontal_positions": horizontal_positions,
            "horizontal_top_temp": horizontal['top_temp'],
            # Rotation
            "rotation_angle": rotation_angle,
            # Reference values for alignment mode
            "reference_hour": hour,
            "reference_minute": minute,
            "reference_temp": horizontal['top_temp']
        }
    }

    # Save to file
    processor = get_processor()
    path = processor._get_calibration_path(template_id)
    with open(path, 'w') as f:
        json.dump(calibration, f, indent=2)

    return calibration


__all__ = [
    'CalibrationProcessor',
    'CalibrationData',
    'Point',
    'DerivedCalibration',
    'save_calibration',
    'save_calibration_full',
    'save_calibration_simple',
    'load_calibration',
    'has_calibration',
]
