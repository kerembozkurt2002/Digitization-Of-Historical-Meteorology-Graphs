#!/usr/bin/env python3
"""Analyze grid lines in thermogram images"""

import sys
import cv2
import numpy as np
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))
from utils.image_utils import load_image

def analyze_grid(image_path: str):
    """Analyze grid lines in the image"""
    image = load_image(image_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    print(f"Image shape: {image.shape}")

    output_dir = Path(image_path).parent

    # Strategy 1: Dark lines on light background
    # The paper is light colored, grid lines are dark
    print("\n=== Strategy 1: Dark pixels (grayscale threshold) ===")

    # Look at grayscale distribution
    print(f"Gray value range: {gray.min()} - {gray.max()}")
    print(f"Gray mean: {gray.mean():.1f}")
    print(f"Gray std: {gray.std():.1f}")

    # Dark pixels
    dark_mask = gray < 100
    print(f"Pixels with gray < 100: {dark_mask.sum()}")

    dark_mask_80 = gray < 80
    print(f"Pixels with gray < 80: {dark_mask_80.sum()}")

    dark_mask_60 = gray < 60
    print(f"Pixels with gray < 60: {dark_mask_60.sum()}")

    # Save dark pixel mask
    cv2.imwrite(str(output_dir / "debug_dark_100.png"), (gray < 100).astype(np.uint8) * 255)
    cv2.imwrite(str(output_dir / "debug_dark_80.png"), (gray < 80).astype(np.uint8) * 255)

    # Strategy 2: Low saturation pixels (non-colored = grid lines?)
    print("\n=== Strategy 2: Low saturation (non-colored) pixels ===")

    s_channel = hsv[:, :, 1]
    v_channel = hsv[:, :, 2]

    # Grid might be dark gray (low saturation, low value)
    low_sat_dark = (s_channel < 50) & (v_channel < 150)
    print(f"Low saturation + dark pixels: {low_sat_dark.sum()}")

    cv2.imwrite(str(output_dir / "debug_low_sat_dark.png"), low_sat_dark.astype(np.uint8) * 255)

    # Strategy 3: Adaptive thresholding
    print("\n=== Strategy 3: Adaptive thresholding ===")

    adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                      cv2.THRESH_BINARY_INV, 11, 2)
    cv2.imwrite(str(output_dir / "debug_adaptive.png"), adaptive)

    # Strategy 4: Look for thin lines using morphology
    print("\n=== Strategy 4: Morphological line detection ===")

    # Detect vertical structures
    kernel_v = np.ones((15, 1), np.uint8)
    vertical = cv2.morphologyEx(adaptive, cv2.MORPH_OPEN, kernel_v)
    cv2.imwrite(str(output_dir / "debug_vertical.png"), vertical)

    # Detect horizontal structures
    kernel_h = np.ones((1, 15), np.uint8)
    horizontal = cv2.morphologyEx(adaptive, cv2.MORPH_OPEN, kernel_h)
    cv2.imwrite(str(output_dir / "debug_horizontal.png"), horizontal)

    # Count lines detected
    lines_v = cv2.HoughLinesP(vertical, 1, np.pi/180, 50, minLineLength=100, maxLineGap=20)
    lines_h = cv2.HoughLinesP(horizontal, 1, np.pi/180, 50, minLineLength=100, maxLineGap=20)

    print(f"Vertical lines detected: {len(lines_v) if lines_v is not None else 0}")
    print(f"Horizontal lines detected: {len(lines_h) if lines_h is not None else 0}")

    # Draw detected lines on image
    result = image.copy()

    if lines_v is not None:
        for line in lines_v:
            x1, y1, x2, y2 = line[0]
            cv2.line(result, (x1, y1), (x2, y2), (0, 255, 0), 2)

    if lines_h is not None:
        for line in lines_h:
            x1, y1, x2, y2 = line[0]
            cv2.line(result, (x1, y1), (x2, y2), (255, 0, 0), 2)

    cv2.imwrite(str(output_dir / "debug_lines_detected.png"), result)
    print(f"\nSaved detected lines to: {output_dir / 'debug_lines_detected.png'}")

    print("\n=== Debug images saved ===")
    print(f"Location: {output_dir}")
    print("- debug_dark_100.png: pixels with gray < 100")
    print("- debug_dark_80.png: pixels with gray < 80")
    print("- debug_low_sat_dark.png: low saturation dark pixels")
    print("- debug_adaptive.png: adaptive threshold")
    print("- debug_vertical.png: vertical structures")
    print("- debug_horizontal.png: horizontal structures")
    print("- debug_lines_detected.png: detected lines overlay")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_grid.py <image_path>")
        sys.exit(1)

    analyze_grid(sys.argv[1])
