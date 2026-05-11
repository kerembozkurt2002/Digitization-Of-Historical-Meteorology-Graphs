"""For each template, run full curve extraction on the first N samples
and emit a 3-row PNG (original / color mask / extracted polyline) under
fix-profiles/<template>/.
"""

import os
import sys
import json
import cv2
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pipeline.color_profiles import get_color_profile
from pipeline.segmenter import CurveSegmenter
from pipeline.preprocessor import Preprocessor

REPO = "/Users/flau/Desktop/Digitization-Of-Historical-Meteorology-Graphs"
DATA = f"{REPO}/data-classified"
OUT_ROOT = f"{REPO}/fix-profiles"
CAL_DIR = f"{REPO}/thermogram-app/backend/calibrations"
N_PER_TEMPLATE = 20

TEMPLATES = [
    ("gunluk", "gunluk-1"),
    ("gunluk", "gunluk-2"),
    ("gunluk", "gunluk-3"),
    ("haftalik", "haftalik-1"),
    ("haftalik", "haftalik-2"),
    ("4_gunluk", "4_gunluk-1"),
    ("4_gunluk", "4_gunluk-2"),
    ("4_gunluk", "4_gunluk-3"),
    ("4_gunluk", "4_gunluk-4"),
]

LABEL_H = 32


def labeled(im, text):
    bar = np.full((LABEL_H, im.shape[1], 3), 60, dtype=np.uint8)
    cv2.putText(bar, text, (12, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    return np.vstack([bar, im])


def overlay_mask(img, mask, color):
    ov = img.copy()
    ov[mask > 0] = color
    return cv2.addWeighted(img, 0.55, ov, 0.45, 0)


def process(chart, tid, seg, preproc):
    src_dir = f"{DATA}/{chart}/{tid}"
    if not os.path.isdir(src_dir):
        print(f"[{tid}] missing source dir {src_dir}")
        return
    out_dir = f"{OUT_ROOT}/{tid}"
    os.makedirs(out_dir, exist_ok=True)

    cal_path = f"{CAL_DIR}/{tid}.json"
    calibration = None
    if os.path.exists(cal_path):
        with open(cal_path) as f:
            calibration = json.load(f)

    profile = get_color_profile(tid)
    files = sorted(
        f for f in os.listdir(src_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff"))
    )[:N_PER_TEMPLATE]
    print(f"[{tid}] {len(files)} files -> {out_dir}")

    for i, name in enumerate(files, 1):
        src = os.path.join(src_dir, name)
        img = cv2.imread(src)
        if img is None:
            print(f"  skip {name} (read failed)")
            continue
        normalized = preproc._normalize(img)

        mask = seg._create_color_mask(normalized, profile)
        mask_blend = overlay_mask(normalized, mask, (0, 255, 0))

        result = seg.extract(
            normalized, calibration, 5,
            None, None, None, None, src, None, None, tid,
        )
        curve_view = normalized.copy()
        n_pts = result.num_points if result.success else 0
        if result.success and n_pts > 1:
            pts = np.array([[int(p.x), int(p.y)] for p in result.points], dtype=np.int32)
            cv2.polylines(curve_view, [pts], False, (0, 0, 255), 3)

        total_px = normalized.shape[0] * normalized.shape[1]
        mask_pct = mask.sum() / 255 / total_px * 100
        stacked = np.vstack([
            labeled(normalized, "1) ORIGINAL"),
            labeled(mask_blend, f"2) COLOR MASK  ({mask_pct:.2f}%)"),
            labeled(curve_view, f"3) FULL EXTRACTION  ({n_pts} pts)"),
        ])
        out_name = os.path.splitext(name)[0] + ".png"
        cv2.imwrite(os.path.join(out_dir, out_name), stacked)
        if i % 5 == 0 or i == len(files):
            print(f"  [{tid}] {i}/{len(files)}")


def main():
    os.makedirs(OUT_ROOT, exist_ok=True)
    import pipeline.segmenter as sg
    sg._dbg = lambda *_: None  # silence per-image logs
    seg = CurveSegmenter()
    preproc = Preprocessor()
    for chart, tid in TEMPLATES:
        process(chart, tid, seg, preproc)
    print("DONE")


if __name__ == "__main__":
    main()
