#!/usr/bin/env python3
"""Debug grid line detection"""

import sys
import cv2
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils.image_utils import load_image

def debug_detection(image_path: str):
    """Debug the grid line detection process"""
    image = load_image(image_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h, w = image.shape[:2]

    print(f"Image size: {w}x{h}")

    # Step 1: Adaptive thresholding
    adaptive = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 11, 2
    )

    # Step 2: Morphological operations for vertical lines
    kernel_v = np.ones((15, 1), np.uint8)
    vertical_mask = cv2.morphologyEx(adaptive, cv2.MORPH_OPEN, kernel_v)

    # Step 3: Morphological operations for horizontal lines
    kernel_h = np.ones((1, 15), np.uint8)
    horizontal_mask = cv2.morphologyEx(adaptive, cv2.MORPH_OPEN, kernel_h)

    print(f"\nVertical mask non-zero pixels: {(vertical_mask > 0).sum()}")
    print(f"Horizontal mask non-zero pixels: {(horizontal_mask > 0).sum()}")

    # Step 4: Hough transform
    print(f"\n=== Hough Transform Parameters ===")
    print(f"Min line length for vertical: {h // 4} (h/4)")
    print(f"Min line length for horizontal: {w // 8} (w/8)")

    # Test different parameters
    for min_len_factor in [2, 4, 8, 16]:
        lines_v = cv2.HoughLinesP(
            vertical_mask,
            rho=1,
            theta=np.pi / 180,
            threshold=50,
            minLineLength=h // min_len_factor,
            maxLineGap=30
        )
        v_count = len(lines_v) if lines_v is not None else 0
        print(f"Vertical lines (minLen=h/{min_len_factor}={h//min_len_factor}): {v_count}")

    for min_len_factor in [4, 8, 16, 32]:
        lines_h = cv2.HoughLinesP(
            horizontal_mask,
            rho=1,
            theta=np.pi / 180,
            threshold=50,
            minLineLength=w // min_len_factor,
            maxLineGap=30
        )
        h_count = len(lines_h) if lines_h is not None else 0
        print(f"Horizontal lines (minLen=w/{min_len_factor}={w//min_len_factor}): {h_count}")

    # Best settings
    print("\n=== Using best settings ===")
    lines_v = cv2.HoughLinesP(
        vertical_mask,
        rho=1,
        theta=np.pi / 180,
        threshold=30,
        minLineLength=h // 8,
        maxLineGap=50
    )

    lines_h = cv2.HoughLinesP(
        horizontal_mask,
        rho=1,
        theta=np.pi / 180,
        threshold=30,
        minLineLength=w // 16,
        maxLineGap=50
    )

    v_count = len(lines_v) if lines_v is not None else 0
    h_count = len(lines_h) if lines_h is not None else 0
    print(f"Vertical lines (threshold=30, minLen=h/8, maxGap=50): {v_count}")
    print(f"Horizontal lines (threshold=30, minLen=w/16, maxGap=50): {h_count}")

    # Analyze line angles
    if lines_v is not None and len(lines_v) > 0:
        print(f"\n=== Vertical Line Analysis ===")
        angles = []
        for line in lines_v[:20]:  # First 20
            x1, y1, x2, y2 = line[0]
            dx = abs(x2 - x1)
            dy = abs(y2 - y1)
            if dx > 0:
                angle = np.arctan(dy / dx) * 180 / np.pi
            else:
                angle = 90
            angles.append(angle)
        print(f"Angle range: {min(angles):.1f}° - {max(angles):.1f}°")
        print(f"Mean angle: {np.mean(angles):.1f}°")

    if lines_h is not None and len(lines_h) > 0:
        print(f"\n=== Horizontal Line Analysis ===")
        angles = []
        for line in lines_h[:20]:  # First 20
            x1, y1, x2, y2 = line[0]
            dx = abs(x2 - x1)
            dy = abs(y2 - y1)
            if dx > 0:
                angle = np.arctan(dy / dx) * 180 / np.pi
            else:
                angle = 90
            angles.append(angle)
        print(f"Angle range: {min(angles):.1f}° - {max(angles):.1f}°")
        print(f"Mean angle: {np.mean(angles):.1f}°")

    # Draw and save result
    output_dir = Path(image_path).parent
    result = image.copy()

    if lines_v is not None:
        for line in lines_v:
            x1, y1, x2, y2 = line[0]
            cv2.line(result, (x1, y1), (x2, y2), (255, 0, 0), 2)

    if lines_h is not None:
        for line in lines_h:
            x1, y1, x2, y2 = line[0]
            cv2.line(result, (x1, y1), (x2, y2), (0, 255, 0), 2)

    output_path = str(output_dir / "debug_raw_lines.png")
    cv2.imwrite(output_path, result)
    print(f"\nSaved raw lines to: {output_path}")

    # Now test clustering
    print("\n=== Clustering Analysis ===")

    def cluster_lines(lines, axis, threshold=15):
        if lines is None or len(lines) == 0:
            return []

        lines = np.array([l[0] for l in lines])

        if axis == 'vertical':
            positions = (lines[:, 0] + lines[:, 2]) / 2
        else:
            positions = (lines[:, 1] + lines[:, 3]) / 2

        sorted_indices = np.argsort(positions)
        sorted_positions = positions[sorted_indices]

        # Count clusters
        clusters = 1
        prev_pos = sorted_positions[0]
        for pos in sorted_positions[1:]:
            if pos - prev_pos >= threshold:
                clusters += 1
            prev_pos = pos

        return clusters

    if lines_v is not None:
        for thresh in [10, 15, 20, 30, 50]:
            clusters = cluster_lines(lines_v, 'vertical', thresh)
            print(f"Vertical clusters (threshold={thresh}px): {clusters}")

    if lines_h is not None:
        for thresh in [10, 15, 20, 30, 50]:
            clusters = cluster_lines(lines_h, 'horizontal', thresh)
            print(f"Horizontal clusters (threshold={thresh}px): {clusters}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_detection.py <image_path>")
        sys.exit(1)

    debug_detection(sys.argv[1])
