#!/usr/bin/env python3
"""Compare slopes before and after dewarping"""

import sys
import cv2
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils.image_utils import load_image
from pipeline.dewarper import Dewarper

def analyze_slopes(image, name):
    """Analyze vertical line slopes in an image"""
    dewarper = Dewarper()
    vertical_segments, _ = dewarper.detect_raw_lines(image)

    slopes = []
    for seg in vertical_segments:
        x1, y1, x2, y2 = seg
        dy = y2 - y1
        dx = x2 - x1

        if abs(dy) > 50:
            slope = dx / dy
            if abs(slope) < 0.5:  # Filter extreme outliers
                slopes.append(slope)

    slopes = np.array(slopes)

    print(f"\n=== {name} ===")
    print(f"Valid segments: {len(slopes)}")
    if len(slopes) > 0:
        print(f"Slope range: {slopes.min():.4f} to {slopes.max():.4f}")
        print(f"Mean slope: {slopes.mean():.4f}")
        print(f"Median slope: {np.median(slopes):.4f}")
        print(f"Std: {slopes.std():.4f}")

        # Ideal: all slopes should be 0 (perfectly vertical)
        # Calculate how far from vertical
        avg_angle = np.arctan(slopes.mean()) * 180 / np.pi
        print(f"Average angle from vertical: {avg_angle:.2f}°")

    return slopes

def main(image_path):
    print(f"Loading: {image_path}")
    original = load_image(image_path)
    h, w = original.shape[:2]
    print(f"Image size: {w}x{h}")

    # Analyze original
    orig_slopes = analyze_slopes(original, "ORIGINAL")

    # Dewarp
    dewarper = Dewarper()
    result = dewarper.dewarp(original)

    if result.success:
        # Analyze dewarped
        dewarp_slopes = analyze_slopes(result.straightened_image, "DEWARPED")

        # Compare
        print(f"\n=== COMPARISON ===")
        if len(orig_slopes) > 0 and len(dewarp_slopes) > 0:
            print(f"Original mean slope:  {orig_slopes.mean():.4f}")
            print(f"Dewarped mean slope:  {dewarp_slopes.mean():.4f}")
            print(f"Improvement: {abs(orig_slopes.mean()) - abs(dewarp_slopes.mean()):.4f}")

            if abs(dewarp_slopes.mean()) < abs(orig_slopes.mean()):
                print("✓ Dewarping reduced slope (good)")
            else:
                print("✗ Dewarping increased slope (bad)")
    else:
        print(f"\nDewarping failed: {result.message}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python compare_slopes.py <image_path>")
        sys.exit(1)

    main(sys.argv[1])
