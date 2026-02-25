#!/usr/bin/env python3
"""Debug line clustering"""

import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils.image_utils import load_image
from pipeline.dewarper import Dewarper

def debug_clusters(image_path):
    image = load_image(image_path)
    h, w = image.shape[:2]
    print(f"Image: {w}x{h}")

    dewarper = Dewarper()
    vertical_segments, _ = dewarper.detect_raw_lines(image)
    print(f"Vertical segments: {len(vertical_segments)}")

    # Collect points
    all_points = []
    for seg in vertical_segments:
        x1, y1, x2, y2 = seg
        all_points.append((x1, y1))
        all_points.append((x2, y2))
        all_points.append(((x1+x2)/2, (y1+y2)/2))

    all_points = np.array(all_points)
    print(f"Total points: {len(all_points)}")

    x_coords = all_points[:, 0]
    y_coords = all_points[:, 1]

    sorted_indices = np.argsort(x_coords)
    sorted_x = x_coords[sorted_indices]
    sorted_y = y_coords[sorted_indices]

    # Test different thresholds
    for threshold in [10, 20, 30, 50]:
        clusters = []
        current_x = [sorted_x[0]]
        current_y = [sorted_y[0]]

        for i in range(1, len(sorted_x)):
            if sorted_x[i] - sorted_x[i-1] < threshold:
                current_x.append(sorted_x[i])
                current_y.append(sorted_y[i])
            else:
                if len(current_x) >= 5:
                    clusters.append((len(current_x), np.mean(current_x)))
                current_x = [sorted_x[i]]
                current_y = [sorted_y[i]]

        if len(current_x) >= 5:
            clusters.append((len(current_x), np.mean(current_x)))

        print(f"\nThreshold {threshold}px: {len(clusters)} clusters (with >=5 points)")
        if len(clusters) > 0:
            sizes = [c[0] for c in clusters]
            print(f"  Cluster sizes: min={min(sizes)}, max={max(sizes)}, avg={np.mean(sizes):.1f}")

    # Show gap distribution
    gaps = np.diff(sorted_x)
    print(f"\n=== Gap Analysis ===")
    print(f"Gap range: {gaps.min():.1f} - {gaps.max():.1f}")
    print(f"Mean gap: {gaps.mean():.1f}")
    print(f"Median gap: {np.median(gaps):.1f}")

    for thresh in [5, 10, 20, 30, 50]:
        pct = (gaps < thresh).sum() / len(gaps) * 100
        print(f"Gaps < {thresh}px: {pct:.1f}%")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_clusters.py <image_path>")
        sys.exit(1)

    debug_clusters(sys.argv[1])
