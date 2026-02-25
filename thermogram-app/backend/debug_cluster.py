#!/usr/bin/env python3
"""Debug clustering algorithm"""

import sys
import cv2
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils.image_utils import load_image

def debug_cluster(image_path: str):
    """Debug clustering of detected lines"""
    image = load_image(image_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h, w = image.shape[:2]

    # Adaptive threshold
    adaptive = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 11, 2
    )

    # Morphological for vertical
    kernel_v = np.ones((15, 1), np.uint8)
    vertical_mask = cv2.morphologyEx(adaptive, cv2.MORPH_OPEN, kernel_v)

    # Hough
    lines_v = cv2.HoughLinesP(
        vertical_mask,
        rho=1,
        theta=np.pi / 180,
        threshold=30,
        minLineLength=h // 8,
        maxLineGap=50
    )

    if lines_v is None:
        print("No lines detected!")
        return

    print(f"Raw lines detected: {len(lines_v)}")

    # Filter by angle (dy > dx)
    filtered = []
    for line in lines_v:
        x1, y1, x2, y2 = line[0]
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        if dy > dx:
            filtered.append(line[0])

    print(f"After angle filter (dy > dx): {len(filtered)}")

    if len(filtered) == 0:
        print("All lines filtered out by angle!")
        return

    # Get positions (x coordinate)
    lines = np.array(filtered)
    positions = (lines[:, 0] + lines[:, 2]) / 2  # Average x

    print(f"\nX positions range: {positions.min():.0f} - {positions.max():.0f}")
    print(f"Image width: {w}")

    # Sort by position
    sorted_indices = np.argsort(positions)
    sorted_positions = positions[sorted_indices]

    # Show gaps between consecutive positions
    gaps = np.diff(sorted_positions)
    print(f"\nGaps between consecutive lines:")
    print(f"  Min gap: {gaps.min():.1f}px")
    print(f"  Max gap: {gaps.max():.1f}px")
    print(f"  Mean gap: {gaps.mean():.1f}px")
    print(f"  Median gap: {np.median(gaps):.1f}px")

    # Show distribution of gaps
    print(f"\nGap distribution:")
    for thresh in [5, 10, 15, 20, 30, 50, 100]:
        count = (gaps < thresh).sum()
        print(f"  Gaps < {thresh}px: {count} ({100*count/len(gaps):.1f}%)")

    # Cluster with threshold 10
    threshold = 10
    clusters = []
    current_cluster = [sorted_positions[0]]

    for i in range(1, len(sorted_positions)):
        if sorted_positions[i] - sorted_positions[i-1] < threshold:
            current_cluster.append(sorted_positions[i])
        else:
            clusters.append(current_cluster)
            current_cluster = [sorted_positions[i]]

    clusters.append(current_cluster)

    print(f"\nClustering with threshold={threshold}px:")
    print(f"Number of clusters: {len(clusters)}")
    print(f"\nCluster sizes: {[len(c) for c in clusters[:20]]}...")

    # Representative positions
    rep_positions = [np.mean(c) for c in clusters]
    print(f"\nRepresentative X positions (first 20):")
    for i, pos in enumerate(rep_positions[:20]):
        print(f"  {i}: x={pos:.0f}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_cluster.py <image_path>")
        sys.exit(1)

    debug_cluster(sys.argv[1])
