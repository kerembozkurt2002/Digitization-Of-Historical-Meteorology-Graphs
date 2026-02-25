#!/usr/bin/env python3
"""Test dewarper directly"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils.image_utils import load_image
from pipeline.dewarper import Dewarper

def test(image_path: str):
    image = load_image(image_path)
    print(f"Image shape: {image.shape}")

    dewarper = Dewarper(debug=True)

    print("\n=== Calling _detect_grid_lines_morphological ===")
    v, h = dewarper._detect_grid_lines_morphological(image)

    print(f"Vertical lines returned: {len(v)}")
    print(f"Horizontal lines returned: {len(h)}")

    if len(v) > 0:
        print(f"\nFirst 5 vertical lines:")
        for i, line in enumerate(v[:5]):
            print(f"  {i}: {line}")

    if len(h) > 0:
        print(f"\nFirst 5 horizontal lines:")
        for i, line in enumerate(h[:5]):
            print(f"  {i}: {line}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_dewarper.py <image_path>")
        sys.exit(1)

    test(sys.argv[1])
