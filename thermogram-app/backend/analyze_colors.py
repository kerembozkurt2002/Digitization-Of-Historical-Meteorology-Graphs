#!/usr/bin/env python3
"""Analyze grid colors in thermogram images"""

import sys
import cv2
import numpy as np
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))
from utils.image_utils import load_image

def analyze_image_colors(image_path: str):
    """Analyze color distribution in the image"""
    image = load_image(image_path)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    print(f"Image shape: {image.shape}")
    print(f"Image dtype: {image.dtype}")

    # Analyze hue distribution
    h_channel = hsv[:, :, 0]
    s_channel = hsv[:, :, 1]
    v_channel = hsv[:, :, 2]

    # Find non-white, non-gray pixels (saturation > 30)
    colored_mask = s_channel > 30

    if colored_mask.sum() > 0:
        colored_hues = h_channel[colored_mask]

        print(f"\n=== Color Analysis ===")
        print(f"Total colored pixels (S > 30): {colored_mask.sum()}")
        print(f"Hue range: {colored_hues.min()} - {colored_hues.max()}")
        print(f"Mean Hue: {colored_hues.mean():.1f}")

        # Histogram of hues
        hist, bins = np.histogram(colored_hues, bins=18, range=(0, 180))

        print(f"\n=== Hue Histogram (colored pixels) ===")
        for i, count in enumerate(hist):
            hue_start = i * 10
            hue_end = (i + 1) * 10
            bar = '#' * (count // 1000)
            if count > 0:
                print(f"Hue {hue_start:3d}-{hue_end:3d}: {count:8d} {bar}")

        # Common color ranges
        print(f"\n=== Common Color Ranges in HSV ===")
        print("Red1:    H=0-10,   S>50, V>50")
        print("Orange:  H=10-25,  S>50, V>50")
        print("Yellow:  H=25-35,  S>50, V>50")
        print("Green:   H=35-85,  S>50, V>50")
        print("Cyan:    H=85-95,  S>50, V>50")
        print("Blue:    H=95-125, S>50, V>50")
        print("Purple:  H=125-155,S>50, V>50")
        print("Red2:    H=170-180,S>50, V>50")

        # Count pixels in each color range
        print(f"\n=== Color Distribution ===")

        color_ranges = [
            ("Red1", 0, 10),
            ("Orange", 10, 25),
            ("Yellow", 25, 35),
            ("Green", 35, 85),
            ("Cyan", 85, 95),
            ("Blue", 95, 125),
            ("Purple", 125, 155),
            ("Magenta", 155, 170),
            ("Red2", 170, 180),
        ]

        for name, h_low, h_high in color_ranges:
            mask = cv2.inRange(hsv, np.array([h_low, 50, 50]), np.array([h_high, 255, 255]))
            count = mask.sum() // 255
            if count > 100:
                print(f"{name:10s}: {count:8d} pixels")

    # Save debug images
    output_dir = Path(image_path).parent

    # Edge detection to see lines
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)

    # Save edge image
    edge_path = str(output_dir / "debug_edges.png")
    cv2.imwrite(edge_path, edges)
    print(f"\nSaved edges to: {edge_path}")

    # Test different color masks
    for name, h_low, h_high in [("orange", 5, 25), ("red", 0, 10), ("green", 35, 85)]:
        mask = cv2.inRange(hsv, np.array([h_low, 50, 50]), np.array([h_high, 255, 255]))
        mask_path = str(output_dir / f"debug_mask_{name}.png")
        cv2.imwrite(mask_path, mask)
        print(f"Saved {name} mask to: {mask_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_colors.py <image_path>")
        sys.exit(1)

    analyze_image_colors(sys.argv[1])
