"""Generate before/after comparison images for templates whose color profile changed.

For each template, processes every file in data-classified/<chart>/<template>/ and
writes a stacked PNG to fix-profiles/<template>/<name>.png with three rows:
  1. Original
  2. Old-profile mask overlay (red)
  3. New-profile mask overlay (green)
"""

import os
import sys
import cv2
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pipeline.color_profiles import (
    ColorProfile,
    DEFAULT_PROFILE,
    GUNLUK_2_PROFILE,
    GUNLUK_3_PROFILE,
    HAFTALIK_2_PROFILE,
)
from pipeline.segmenter import CurveSegmenter

REPO = "/Users/flau/Desktop/Digitization-Of-Historical-Meteorology-Graphs"

# Pre-fix profiles. Kept here so the comparison stays reproducible after the
# committed profiles change again.
OLD_GUNLUK_2 = ColorProfile(
    max_intensity=160, min_intensity=30,
    rg_diff_min=-20, rg_diff_max=25,
    rb_diff_min=-40,
    bg_diff_min=-50, bg_diff_max=40,
    sat_min=0, sat_max=45,
    use_grayscale_detection=True,
    grayscale_max_sat=30, grayscale_max_intensity=130,
    description="OLD gunluk-2 (gray-pencil)",
)
OLD_GUNLUK_3 = ColorProfile(
    max_intensity=180, min_intensity=0,
    rg_diff_min=-50, rg_diff_max=45,
    rb_diff_min=-60, bg_diff_min=-100, bg_diff_max=50,
    sat_min=0, sat_max=70,
    use_grayscale_detection=False,
    description="OLD gunluk-3 (dark-blue strict)",
)
# Old haftalik-2 used the DEFAULT (pinkish) profile.
OLD_HAFTALIK_2 = DEFAULT_PROFILE

TARGETS = [
    {
        "tid": "gunluk-2",
        "src_dir": f"{REPO}/data-classified/gunluk/gunluk-2",
        "old": OLD_GUNLUK_2,
        "new": GUNLUK_2_PROFILE,
    },
    {
        "tid": "gunluk-3",
        "src_dir": f"{REPO}/data-classified/gunluk/gunluk-3",
        "old": OLD_GUNLUK_3,
        "new": GUNLUK_3_PROFILE,
    },
    {
        "tid": "haftalik-2",
        "src_dir": f"{REPO}/data-classified/haftalik/haftalik-2",
        "old": OLD_HAFTALIK_2,
        "new": HAFTALIK_2_PROFILE,
    },
]

OUT_ROOT = f"{REPO}/fix-profiles"

LABEL_H = 30


def labeled(img: np.ndarray, text: str) -> np.ndarray:
    h, w = img.shape[:2]
    bar = np.full((LABEL_H, w, 3), 60, dtype=np.uint8)
    cv2.putText(bar, text, (12, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    return np.vstack([bar, img])


def overlay(img: np.ndarray, mask: np.ndarray, color) -> np.ndarray:
    ov = img.copy()
    ov[mask > 0] = color
    return cv2.addWeighted(img, 0.55, ov, 0.45, 0)


def process_template(target, seg: CurveSegmenter):
    tid = target["tid"]
    out_dir = f"{OUT_ROOT}/{tid}"
    os.makedirs(out_dir, exist_ok=True)
    files = sorted(
        f for f in os.listdir(target["src_dir"])
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff"))
    )
    print(f"[{tid}] {len(files)} files -> {out_dir}")
    for i, name in enumerate(files, 1):
        src = os.path.join(target["src_dir"], name)
        img = cv2.imread(src)
        if img is None:
            print(f"  skip {name} (read failed)")
            continue
        old_mask = seg._create_color_mask(img, target["old"])
        new_mask = seg._create_color_mask(img, target["new"])
        total_px = img.shape[0] * img.shape[1]
        old_pct = old_mask.sum() / 255 / total_px * 100
        new_pct = new_mask.sum() / 255 / total_px * 100
        old_view = overlay(img, old_mask, (0, 0, 255))   # red
        new_view = overlay(img, new_mask, (0, 255, 0))   # green
        stacked = np.vstack([
            labeled(img, "ORIGINAL"),
            labeled(old_view, f"OLD profile ({old_pct:.2f}%)"),
            labeled(new_view, f"NEW profile ({new_pct:.2f}%)"),
        ])
        out_name = os.path.splitext(name)[0] + ".png"
        cv2.imwrite(os.path.join(out_dir, out_name), stacked)
        if i % 25 == 0 or i == len(files):
            print(f"  [{tid}] {i}/{len(files)}")


def main():
    os.makedirs(OUT_ROOT, exist_ok=True)
    seg = CurveSegmenter()
    # Suppress per-image debug noise from the segmenter
    import pipeline.segmenter as sg
    sg._dbg = lambda *_: None  # type: ignore
    for target in TARGETS:
        process_template(target, seg)
    print("DONE")


if __name__ == "__main__":
    main()
