#!/usr/bin/env python3
"""
Thermogram Backend CLI

This is the main entry point for the Python sidecar.
It provides CLI commands for processing thermogram images.
"""

import argparse
import json
import sys
import os
from pathlib import Path

import cv2
import numpy as np

from pipeline.dewarper import Dewarper
from pipeline.preprocessor import Preprocessor
from pipeline.template_detector import TemplateDetector
from utils.image_utils import load_image, encode_image_base64, save_image


def cmd_preview(args):
    """Generate a preview with detected grid lines using specified algorithm."""
    image_path = args.image
    algorithm = getattr(args, 'algorithm', 1)
    curvature = getattr(args, 'curvature', None)

    if not os.path.exists(image_path):
        result = {
            "success": False,
            "error": f"Image file not found: {image_path}"
        }
        print(json.dumps(result))
        return 1

    try:
        try:
            image = load_image(image_path)
        except ValueError as e:
            result = {
                "success": False,
                "error": str(e)
            }
            print(json.dumps(result))
            return 1

        # Normalize image (no automatic deskew - rotation is handled manually by user)
        preprocessor = Preprocessor()
        normalized_image = preprocessor._normalize(image)

        dewarper = Dewarper(debug=False)
        overlay_result = dewarper.create_grid_overlay(normalized_image, algorithm, curvature_override=curvature)

        response = {
            "success": overlay_result.success,
            "vertical_lines": overlay_result.vertical_lines,
            "horizontal_lines": overlay_result.horizontal_lines,
            "preview_image": encode_image_base64(overlay_result.overlay_image),
            "message": overlay_result.message,
            # Line positions for client-side rendering (convert numpy int64 to Python int)
            "vertical_line_positions": [int(x) for x in overlay_result.vertical_line_positions],
            "horizontal_line_positions": [int(y) for y in overlay_result.horizontal_line_positions],
            "image_height": int(overlay_result.image_height),
            "image_width": int(overlay_result.image_width),
            # Curve coefficients for vertical lines: x = a*y² + b*y + x0
            "curve_coeff_a": float(overlay_result.curve_coeff_a),
            "curve_coeff_b": float(overlay_result.curve_coeff_b)
        }

        if args.output:
            save_image(overlay_result.overlay_image, args.output)
            response["output_path"] = args.output

        print(json.dumps(response))
        return 0

    except Exception as e:
        result = {
            "success": False,
            "error": str(e)
        }
        print(json.dumps(result))
        return 1


def cmd_detect_template(args):
    """Detect thermogram template type."""
    image_path = args.image

    if not os.path.exists(image_path):
        result = {
            "success": False,
            "error": f"Image file not found: {image_path}"
        }
        print(json.dumps(result))
        return 1

    try:
        try:
            image = load_image(image_path)
        except ValueError as e:
            result = {
                "success": False,
                "error": str(e)
            }
            print(json.dumps(result))
            return 1

        # Detect template
        detector = TemplateDetector()
        match = detector.detect(image)

        # Get template metadata
        template_info = detector.TEMPLATES.get(match.template_id, {})

        response = {
            "success": True,
            "template_id": match.template_id,
            "chart_type": match.chart_type,
            "confidence": round(match.confidence, 4),
            "period": template_info.get("period", "unknown"),
            "grid_color": template_info.get("grid_color", "unknown"),
            "all_scores": {k: round(v, 4) for k, v in sorted(match.all_scores.items(), key=lambda x: -x[1])}
        }

        print(json.dumps(response))
        return 0

    except Exception as e:
        result = {
            "success": False,
            "error": str(e)
        }
        print(json.dumps(result))
        return 1


def cmd_get_calibration(args):
    """Get grid calibration data for a template."""
    template_id = args.template_id

    try:
        # Load calibration file directly
        from pipeline.calibration_processor import get_processor
        processor = get_processor()
        path = processor._get_calibration_path(template_id)

        if not path.exists():
            response = {
                "success": True,
                "exists": False,
                "template_id": template_id
            }
        else:
            with open(path, 'r') as f:
                data = json.load(f)

            # Return the derived data directly
            derived = data.get('derived', {})
            vertical = data.get('vertical', {})
            horizontal = data.get('horizontal', {})

            # Parse reference time from "HH:MM" format
            ref_time = vertical.get('line1_hour', '12:00')
            ref_hour, ref_minute = 12, 0
            if ':' in str(ref_time):
                parts = str(ref_time).split(':')
                ref_hour = int(parts[0]) if parts[0].isdigit() else 12
                ref_minute = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0

            # Get horizontal top Y from calibration data
            horizontal_top_y = 0
            if 'horizontal' in data and 'top' in data['horizontal']:
                horizontal_top_y = data['horizontal']['top'].get('y', 0)

            response = {
                "success": True,
                "exists": True,
                "template_id": data.get('template_id', template_id),
                "calibrated_at": data.get('calibrated_at', ''),
                "image_dimensions": data.get('image_dimensions', {}),
                "derived": {
                    "top_point": derived.get('top_point', {"x": 0, "y": 0}),
                    "bottom_point": derived.get('bottom_point', {"x": 0, "y": 0}),
                    "curve_center_y": derived.get('curve_center_y', 0),
                    "curve_coeff_a": derived.get('curve_coeff_a', 0),
                    "line_spacing": derived.get('line_spacing', 50),
                    "line_positions": derived.get('line_positions', []),
                    # Horizontal data
                    "horizontal_spacing": derived.get('horizontal_spacing', 0),
                    "horizontal_positions": derived.get('horizontal_positions', []),
                    "horizontal_top_temp": derived.get('horizontal_top_temp', horizontal.get('top_temp', 0)),
                    "horizontal_top_y": horizontal_top_y,
                    # Reference values for alignment mode
                    "reference_hour": ref_hour,
                    "reference_minute": ref_minute,
                    "reference_temp": horizontal.get('top_temp', derived.get('horizontal_top_temp', 0))
                }
            }

        print(json.dumps(response))
        return 0

    except Exception as e:
        result = {
            "success": False,
            "error": str(e)
        }
        print(json.dumps(result))
        return 1


def cmd_save_calibration_simple(args):
    """Save simplified grid calibration data (7-step system with pixel spacing)."""
    from pipeline.calibration_processor import save_calibration_simple

    try:
        data = json.loads(args.data)

        calibration = save_calibration_simple(data)

        response = {
            "success": True,
            "template_id": calibration["template_id"],
            "calibrated_at": calibration["calibrated_at"],
            "line_spacing": calibration["derived"]["line_spacing"],
            "curve_coeff_a": calibration["derived"]["curve_coeff_a"],
            "curve_center_y": calibration["derived"]["curve_center_y"]
        }

        print(json.dumps(response))
        return 0

    except Exception as e:
        result = {
            "success": False,
            "error": str(e)
        }
        print(json.dumps(result))
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Thermogram Digitization Backend",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Preview command
    preview_parser = subparsers.add_parser('preview', help='Preview grid detection')
    preview_parser.add_argument('--image', '-i', required=True, help='Path to input image')
    preview_parser.add_argument('--output', '-o', help='Path to save preview image')
    preview_parser.add_argument('--algorithm', '-a', type=int, default=1,
                                help='Algorithm: 0=Original, 4=Horizontal, 5=Vertical, 6=Combined')
    preview_parser.add_argument('--curvature', '-c', type=float, default=None,
                                help='Vertical line curvature override (0.0=straight, 1.0=max curve)')
    preview_parser.set_defaults(func=cmd_preview)

    # Detect template command
    detect_parser = subparsers.add_parser('detect-template', help='Detect thermogram template type')
    detect_parser.add_argument('--image', '-i', required=True, help='Path to input image')
    detect_parser.set_defaults(func=cmd_detect_template)

    # Get calibration command
    get_cal_parser = subparsers.add_parser('get-calibration', help='Get grid calibration for a template')
    get_cal_parser.add_argument('--template-id', '-t', required=True, help='Template ID (e.g., gunluk-1)')
    get_cal_parser.set_defaults(func=cmd_get_calibration)

    # Save simple calibration command (7-step system with pixel spacing)
    save_cal_simple_parser = subparsers.add_parser('save-calibration-simple', help='Save grid calibration')
    save_cal_simple_parser.add_argument('--data', '-d', required=True, help='JSON object with calibration data')
    save_cal_simple_parser.set_defaults(func=cmd_save_calibration_simple)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
