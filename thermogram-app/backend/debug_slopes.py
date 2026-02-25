#!/usr/bin/env python3
"""Debug line slopes to understand the distortion"""

import sys
import cv2
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils.image_utils import load_image
from pipeline.dewarper import Dewarper

def debug_slopes(image_path: str):
    image = load_image(image_path)
    h, w = image.shape[:2]
    print(f"Image size: {w}x{h}")

    dewarper = Dewarper(debug=True)
    vertical_segments, horizontal_segments = dewarper.detect_raw_lines(image)

    print(f"\nVertical segments: {len(vertical_segments)}")
    print(f"Horizontal segments: {len(horizontal_segments)}")

    # Analyze vertical line slopes
    slopes = []
    for seg in vertical_segments:
        x1, y1, x2, y2 = seg
        dy = y2 - y1
        dx = x2 - x1

        if abs(dy) > 50:  # Significant vertical extent
            slope = dx / dy  # x change per y unit
            x_center = (x1 + x2) / 2
            slopes.append((x_center, slope))

    if len(slopes) == 0:
        print("No valid slopes found!")
        return

    slopes = np.array(slopes)
    x_positions = slopes[:, 0]
    slope_values = slopes[:, 1]

    print(f"\n=== Slope Analysis ===")
    print(f"Valid segments: {len(slopes)}")
    print(f"Slope range: {slope_values.min():.4f} to {slope_values.max():.4f}")
    print(f"Mean slope: {slope_values.mean():.4f}")
    print(f"Std slope: {slope_values.std():.4f}")

    # What does this slope mean?
    # slope = 0.01 means for every 100 pixels down, the line moves 1 pixel right
    # For a 1000 pixel tall image, total drift = slope * 1000

    print(f"\n=== Drift Calculation ===")
    avg_slope = slope_values.mean()
    total_drift = avg_slope * h
    print(f"Average slope: {avg_slope:.4f} px/px")
    print(f"For image height {h}px:")
    print(f"  Total x-drift from top to bottom: {total_drift:.1f} pixels")

    # Show slope at different x positions
    print(f"\n=== Slope by X Position ===")
    for x_target in [w*0.1, w*0.25, w*0.5, w*0.75, w*0.9]:
        # Find nearby slopes
        distances = np.abs(x_positions - x_target)
        nearby_mask = distances < 100
        if nearby_mask.sum() > 0:
            local_slope = slope_values[nearby_mask].mean()
            local_drift = local_slope * h
            print(f"  x={x_target:.0f}: slope={local_slope:.4f}, drift={local_drift:.1f}px")

    # Draw visualization
    output = image.copy()

    # Draw some vertical segments with their slopes
    for i, seg in enumerate(vertical_segments[:100]):
        x1, y1, x2, y2 = seg
        cv2.line(output, (x1, y1), (x2, y2), (0, 0, 255), 1)

    # Draw reference vertical lines (what straight should look like)
    for x in range(0, w, 200):
        cv2.line(output, (x, 0), (x, h-1), (0, 255, 0), 1)

    output_path = Path(image_path).parent / "debug_slopes.png"
    cv2.imwrite(str(output_path), output)
    print(f"\nSaved visualization to: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_slopes.py <image_path>")
        sys.exit(1)

    debug_slopes(sys.argv[1])
