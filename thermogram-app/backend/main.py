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
import base64
from pathlib import Path

import cv2
import numpy as np

from pipeline.dewarper import Dewarper
from utils.image_utils import load_image, encode_image_base64, save_image


def cmd_dewarp(args):
    """Dewarp a thermogram image."""
    image_path = args.image

    if not os.path.exists(image_path):
        result = {
            "success": False,
            "error": f"Image file not found: {image_path}"
        }
        print(json.dumps(result))
        return 1

    try:
        # Load image using Pillow (handles old TIFF formats)
        try:
            image = load_image(image_path)
        except ValueError as e:
            result = {
                "success": False,
                "error": str(e)
            }
            print(json.dumps(result))
            return 1

        # Dewarp
        dewarper = Dewarper(debug=False)
        dewarp_result = dewarper.dewarp(image)

        # Prepare response
        response = {
            "success": dewarp_result.success,
            "message": dewarp_result.message,
            "grid_lines_detected": dewarp_result.grid_lines_detected,
        }

        if dewarp_result.success:
            # Encode images as base64
            response["original_image"] = encode_image_base64(dewarp_result.original_image)
            response["straightened_image"] = encode_image_base64(dewarp_result.straightened_image)

            # Include transform matrices
            response["forward_transform"] = dewarp_result.forward_transform.tolist()
            response["inverse_transform"] = dewarp_result.inverse_transform.tolist()

            # Save output if specified
            if args.output:
                save_image(dewarp_result.straightened_image, args.output)
                response["output_path"] = args.output

        print(json.dumps(response))
        return 0 if dewarp_result.success else 1

    except Exception as e:
        result = {
            "success": False,
            "error": str(e)
        }
        print(json.dumps(result))
        return 1


def cmd_preview(args):
    """Generate a preview with detected grid lines using specified algorithm."""
    image_path = args.image
    algorithm = getattr(args, 'algorithm', 1)

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

        dewarper = Dewarper(debug=False)
        overlay_result = dewarper.create_grid_overlay(image, algorithm)

        response = {
            "success": overlay_result.success,
            "vertical_lines": overlay_result.vertical_lines,
            "horizontal_lines": overlay_result.horizontal_lines,
            "preview_image": encode_image_base64(overlay_result.overlay_image),
            "message": overlay_result.message
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


def cmd_flattened(args):
    """Generate a flattened grid visualization (normalized/straightened grid lines only)."""
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

        dewarper = Dewarper(debug=False)
        flatten_result = dewarper.create_flattened_grid(image)

        response = {
            "success": flatten_result.success,
            "message": flatten_result.message,
            "vertical_lines": flatten_result.vertical_lines,
            "horizontal_lines": flatten_result.horizontal_lines,
            "flattened_image": encode_image_base64(flatten_result.flattened_image)
        }

        if args.output:
            save_image(flatten_result.flattened_image, args.output)
            response["output_path"] = args.output

        print(json.dumps(response))
        return 0 if flatten_result.success else 1

    except Exception as e:
        result = {
            "success": False,
            "error": str(e)
        }
        print(json.dumps(result))
        return 1


def cmd_straightened_grid(args):
    """Generate final straightened/dewarped image (no colored overlay)."""
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

        dewarper = Dewarper(debug=False)
        straightened_result = dewarper.create_straightened_image(image)

        response = {
            "success": straightened_result.success,
            "message": straightened_result.message,
            "vertical_lines": straightened_result.vertical_lines,
            "horizontal_lines": straightened_result.horizontal_lines,
            "straightened_grid_image": encode_image_base64(straightened_result.flattened_image)
        }

        if args.output:
            save_image(straightened_result.flattened_image, args.output)
            response["output_path"] = args.output

        print(json.dumps(response))
        return 0 if straightened_result.success else 1

    except Exception as e:
        result = {
            "success": False,
            "error": str(e)
        }
        print(json.dumps(result))
        return 1


def cmd_health(args):
    """Health check command."""
    result = {
        "success": True,
        "message": "Backend is running",
        "version": "1.0.0"
    }
    print(json.dumps(result))
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Thermogram Digitization Backend",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Dewarp command
    dewarp_parser = subparsers.add_parser('dewarp', help='Dewarp a thermogram image')
    dewarp_parser.add_argument('--image', '-i', required=True, help='Path to input image')
    dewarp_parser.add_argument('--output', '-o', help='Path to save dewarped image')
    dewarp_parser.set_defaults(func=cmd_dewarp)

    # Preview command
    preview_parser = subparsers.add_parser('preview', help='Preview grid detection')
    preview_parser.add_argument('--image', '-i', required=True, help='Path to input image')
    preview_parser.add_argument('--output', '-o', help='Path to save preview image')
    preview_parser.add_argument('--algorithm', '-a', type=int, default=1,
                                help='Algorithm: 1=Canny+Hough, 2=VerticalGradient, 3=LSD, 4=Adaptive+Morphological')
    preview_parser.set_defaults(func=cmd_preview)

    # Flattened grid command
    flattened_parser = subparsers.add_parser('flattened', help='Generate flattened grid visualization')
    flattened_parser.add_argument('--image', '-i', required=True, help='Path to input image')
    flattened_parser.add_argument('--output', '-o', help='Path to save flattened grid image')
    flattened_parser.set_defaults(func=cmd_flattened)

    # Straightened grid command
    straightened_parser = subparsers.add_parser('straightened-grid', help='Generate straightened grid only')
    straightened_parser.add_argument('--image', '-i', required=True, help='Path to input image')
    straightened_parser.add_argument('--output', '-o', help='Path to save straightened grid image')
    straightened_parser.set_defaults(func=cmd_straightened_grid)

    # Health check command
    health_parser = subparsers.add_parser('health', help='Health check')
    health_parser.set_defaults(func=cmd_health)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
