#!/usr/bin/env python3
"""
Annotation Utilities

Cleans noisy freehand curve annotations and analyzes pixel properties
at ground-truth curve locations to inform segmenter tuning.

Usage:
    python annotation_utils.py clean                 # clean all annotations
    python annotation_utils.py analyze               # analyze cleaned annotations against images
    python annotation_utils.py clean --file X.json   # clean a single file
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np
from scipy.signal import savgol_filter


def load_annotation(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def _clean_points(xs: np.ndarray, ys: np.ndarray, smooth_window: int = 15, smooth_poly: int = 3):
    """Clean a single set of freehand points.

    Returns (x_clean, y_clean) numpy arrays, or (None, None) if too few
    points survive.
    """
    if len(xs) < 2:
        return None, None

    # 1. Deduplicate consecutive near-identical points
    keep = [0]
    for i in range(1, len(xs)):
        if abs(xs[i] - xs[keep[-1]]) >= 0.5 or abs(ys[i] - ys[keep[-1]]) >= 0.5:
            keep.append(i)
    xs, ys = xs[keep], ys[keep]

    # 2. Enforce monotonically increasing X
    mono = [0]
    for i in range(1, len(xs)):
        if xs[i] > xs[mono[-1]]:
            mono.append(i)
    xs, ys = xs[mono], ys[mono]

    if len(xs) < 2:
        return None, None

    # 3. Resample to uniform 1px X spacing
    x_uniform = np.arange(int(np.ceil(xs[0])), int(np.floor(xs[-1])) + 1, dtype=np.float64)
    y_uniform = np.interp(x_uniform, xs, ys)

    # 4. Savitzky-Golay smoothing
    win = min(smooth_window, len(y_uniform))
    if win % 2 == 0:
        win -= 1
    if win >= 5:
        y_smooth = savgol_filter(y_uniform, window_length=win, polyorder=smooth_poly)
    else:
        y_smooth = y_uniform

    return x_uniform, y_smooth


def clean_annotation(raw: dict, smooth_window: int = 15, smooth_poly: int = 3) -> dict:
    """Clean a raw freehand annotation.

    If the annotation contains separate strokes, each stroke is cleaned
    independently and the results are concatenated (sorted by X) with
    natural gaps preserved.  This prevents false interpolation across
    regions where no curve was drawn.

    Pipeline per stroke:
      1. Deduplicate consecutive near-identical points
      2. Enforce monotonically increasing X
      3. Resample to uniform 1px X spacing via linear interpolation
      4. Savitzky-Golay smooth the Y values
    """
    strokes = raw.get("strokes")

    if strokes and len(strokes) > 0:
        # Multi-stroke: clean each stroke independently
        all_cleaned_pts = []
        for stroke in strokes:
            s_pts = stroke.get("points", [])
            if len(s_pts) < 2:
                continue
            s_xs = np.array([p["x"] for p in s_pts])
            s_ys = np.array([p["y"] for p in s_pts])
            xc, yc = _clean_points(s_xs, s_ys, smooth_window, smooth_poly)
            if xc is not None:
                for i in range(len(xc)):
                    all_cleaned_pts.append({"x": float(xc[i]), "y": float(yc[i])})

        all_cleaned_pts.sort(key=lambda p: p["x"])

        if len(all_cleaned_pts) < 2:
            return raw

        return {
            "image_path": raw["image_path"],
            "template_id": raw["template_id"],
            "annotated_at": raw["annotated_at"],
            "num_points": len(all_cleaned_pts),
            "raw_num_points": raw.get("num_points", len(raw.get("points", []))),
            "points": all_cleaned_pts,
        }

    # Single-stroke fallback (backward compat for old annotations)
    pts = raw["points"]
    if len(pts) < 2:
        return raw

    xs = np.array([p["x"] for p in pts])
    ys = np.array([p["y"] for p in pts])
    xc, yc = _clean_points(xs, ys, smooth_window, smooth_poly)
    if xc is None:
        return raw

    cleaned_pts = [{"x": float(xc[i]), "y": float(yc[i])} for i in range(len(xc))]

    return {
        "image_path": raw["image_path"],
        "template_id": raw["template_id"],
        "annotated_at": raw["annotated_at"],
        "num_points": len(cleaned_pts),
        "raw_num_points": raw["num_points"],
        "points": cleaned_pts,
    }


def analyze_annotation(cleaned_path: str, image_path: str, off_curve_offset: int = 30) -> dict:
    """Analyze pixel properties at curve vs. off-curve locations.

    Returns a dict with per-image statistics.
    """
    sys.path.insert(0, str(Path(__file__).parent))
    from utils.image_utils import load_image
    from pipeline.preprocessor import Preprocessor

    ann = load_annotation(cleaned_path)
    pts = ann["points"]

    image = load_image(image_path)
    preprocessor = Preprocessor()
    normalized = preprocessor._normalize(image)

    gray = cv2.cvtColor(normalized, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(normalized, cv2.COLOR_BGR2HSV)
    h_img, w_img = gray.shape[:2]

    curve_gray, curve_h, curve_s, curve_v = [], [], [], []
    off_gray, off_h, off_s, off_v = [], [], [], []
    curve_ink_scores, off_ink_scores = [], []

    for p in pts:
        x, y = int(round(p["x"])), int(round(p["y"]))
        if x < 1 or x >= w_img - 1 or y < 1 or y >= h_img - 1:
            continue

        # 3x3 patch at curve location
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                py, px = y + dy, x + dx
                g = int(gray[py, px])
                hh = int(hsv[py, px, 0])
                ss = int(hsv[py, px, 1])
                vv = int(hsv[py, px, 2])
                ink = (255 - g) * (255 - ss) / 255.0

                curve_gray.append(g)
                curve_h.append(hh)
                curve_s.append(ss)
                curve_v.append(vv)
                curve_ink_scores.append(ink)

        # Off-curve: y +/- offset
        for y_off in (y - off_curve_offset, y + off_curve_offset):
            if y_off < 1 or y_off >= h_img - 1:
                continue
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    py, px = y_off + dy, x + dx
                    g = int(gray[py, px])
                    hh = int(hsv[py, px, 0])
                    ss = int(hsv[py, px, 1])
                    vv = int(hsv[py, px, 2])
                    ink = (255 - g) * (255 - ss) / 255.0

                    off_gray.append(g)
                    off_h.append(hh)
                    off_s.append(ss)
                    off_v.append(vv)
                    off_ink_scores.append(ink)

    # Slope analysis
    xs = np.array([p["x"] for p in pts])
    ys = np.array([p["y"] for p in pts])
    if len(xs) > 1:
        dydx = np.abs(np.diff(ys) / np.maximum(np.diff(xs), 0.01))
        max_slope = float(np.max(dydx))
        mean_slope = float(np.mean(dydx))
        p95_slope = float(np.percentile(dydx, 95))
    else:
        max_slope = mean_slope = p95_slope = 0.0

    # Deviation from linear interpolation
    if len(xs) > 2:
        linear_y = np.interp(xs, [xs[0], xs[-1]], [ys[0], ys[-1]])
        deviations = np.abs(ys - linear_y)
        mean_dev = float(np.mean(deviations))
        max_dev = float(np.max(deviations))
    else:
        mean_dev = max_dev = 0.0

    def stats(arr):
        a = np.array(arr, dtype=np.float64)
        return {"mean": float(np.mean(a)), "std": float(np.std(a)),
                "min": float(np.min(a)), "max": float(np.max(a)),
                "p25": float(np.percentile(a, 25)), "p75": float(np.percentile(a, 75))}

    return {
        "image": os.path.basename(image_path),
        "num_points": len(pts),
        "x_range": [float(xs[0]), float(xs[-1])],
        "y_range": [float(ys.min()), float(ys.max())],
        "curve": {
            "gray": stats(curve_gray),
            "hue": stats(curve_h),
            "sat": stats(curve_s),
            "val": stats(curve_v),
            "ink_score": stats(curve_ink_scores),
        },
        "off_curve": {
            "gray": stats(off_gray),
            "hue": stats(off_h),
            "sat": stats(off_s),
            "val": stats(off_v),
            "ink_score": stats(off_ink_scores),
        },
        "slope": {
            "max": max_slope,
            "mean": mean_slope,
            "p95": p95_slope,
        },
        "deviation_from_linear": {
            "mean": mean_dev,
            "max": max_dev,
        },
    }


def cmd_clean(args):
    ann_dir = Path(__file__).parent.parent / "annotations"
    cleaned_dir = ann_dir / "cleaned"
    cleaned_dir.mkdir(parents=True, exist_ok=True)

    if args.file:
        files = [Path(args.file)]
    else:
        files = sorted(f for f in ann_dir.glob("*.json") if f.name != "analysis_results.json")

    for f in files:
        print(f"Cleaning {f.name}...")
        raw = load_annotation(str(f))
        cleaned = clean_annotation(raw)
        out_path = cleaned_dir / f.name
        with open(out_path, "w") as fh:
            json.dump(cleaned, fh, indent=2)
        print(f"  Raw: {raw['num_points']} pts -> Cleaned: {cleaned['num_points']} pts -> {out_path.name}")


def cmd_analyze(args):
    ann_dir = Path(__file__).parent.parent / "annotations"
    cleaned_dir = ann_dir / "cleaned"

    if not cleaned_dir.exists():
        print("No cleaned annotations found. Run 'clean' first.")
        return 1

    files = sorted(cleaned_dir.glob("*.json"))
    if not files:
        print("No cleaned annotation files found.")
        return 1

    all_results = []
    for f in files:
        ann = load_annotation(str(f))
        img_path = ann["image_path"]

        if not os.path.exists(img_path):
            print(f"  SKIP {f.name}: image not found at {img_path}")
            continue

        print(f"Analyzing {f.name}...")
        result = analyze_annotation(str(f), img_path)
        all_results.append(result)

        # Per-image summary
        c = result["curve"]
        o = result["off_curve"]
        print(f"  Points: {result['num_points']}")
        print(f"  X: [{result['x_range'][0]:.0f}, {result['x_range'][1]:.0f}]")
        print(f"  Y: [{result['y_range'][0]:.0f}, {result['y_range'][1]:.0f}]")
        print(f"  Curve  gray: {c['gray']['mean']:.1f} +/- {c['gray']['std']:.1f}   sat: {c['sat']['mean']:.1f} +/- {c['sat']['std']:.1f}   hue: {c['hue']['mean']:.1f} +/- {c['hue']['std']:.1f}   ink_score: {c['ink_score']['mean']:.1f} +/- {c['ink_score']['std']:.1f}")
        print(f"  Off    gray: {o['gray']['mean']:.1f} +/- {o['gray']['std']:.1f}   sat: {o['sat']['mean']:.1f} +/- {o['sat']['std']:.1f}   hue: {o['hue']['mean']:.1f} +/- {o['hue']['std']:.1f}   ink_score: {o['ink_score']['mean']:.1f} +/- {o['ink_score']['std']:.1f}")
        print(f"  Ink score ratio (curve/off): {c['ink_score']['mean'] / max(o['ink_score']['mean'], 0.01):.2f}x")
        print(f"  Slope  max: {result['slope']['max']:.3f}  p95: {result['slope']['p95']:.3f}  mean: {result['slope']['mean']:.3f}")
        print(f"  Deviation from linear  mean: {result['deviation_from_linear']['mean']:.1f}px  max: {result['deviation_from_linear']['max']:.1f}px")
        print()

    # Aggregate
    if len(all_results) >= 2:
        print("=" * 70)
        print("AGGREGATE across all images:")
        all_curve_ink = [r["curve"]["ink_score"]["mean"] for r in all_results]
        all_off_ink = [r["off_curve"]["ink_score"]["mean"] for r in all_results]
        all_curve_gray = [r["curve"]["gray"]["mean"] for r in all_results]
        all_off_gray = [r["off_curve"]["gray"]["mean"] for r in all_results]
        all_curve_sat = [r["curve"]["sat"]["mean"] for r in all_results]
        all_off_sat = [r["off_curve"]["sat"]["mean"] for r in all_results]
        all_curve_hue = [r["curve"]["hue"]["mean"] for r in all_results]
        all_slopes_max = [r["slope"]["max"] for r in all_results]
        all_slopes_p95 = [r["slope"]["p95"] for r in all_results]
        all_dev_mean = [r["deviation_from_linear"]["mean"] for r in all_results]
        all_dev_max = [r["deviation_from_linear"]["max"] for r in all_results]

        print(f"  Curve ink_score avg: {np.mean(all_curve_ink):.1f}  Off avg: {np.mean(all_off_ink):.1f}  Ratio: {np.mean(all_curve_ink)/max(np.mean(all_off_ink),0.01):.2f}x")
        print(f"  Curve gray avg: {np.mean(all_curve_gray):.1f}  Off gray avg: {np.mean(all_off_gray):.1f}")
        print(f"  Curve sat avg: {np.mean(all_curve_sat):.1f}  Off sat avg: {np.mean(all_off_sat):.1f}")
        print(f"  Curve hue avg: {np.mean(all_curve_hue):.1f}")
        print(f"  Max slope across all: {max(all_slopes_max):.3f}  p95 avg: {np.mean(all_slopes_p95):.3f}")
        print(f"  Linear deviation  mean avg: {np.mean(all_dev_mean):.1f}px  max: {max(all_dev_max):.1f}px")

    # Save full results
    results_path = ann_dir / "analysis_results.json"
    with open(results_path, "w") as fh:
        json.dump(all_results, fh, indent=2)
    print(f"\nFull results saved to {results_path}")


def main():
    parser = argparse.ArgumentParser(description="Annotation utilities")
    subparsers = parser.add_subparsers(dest="command")

    clean_parser = subparsers.add_parser("clean", help="Clean raw annotations")
    clean_parser.add_argument("--file", "-f", default=None, help="Single file to clean")

    subparsers.add_parser("analyze", help="Analyze cleaned annotations against images")

    args = parser.parse_args()
    if args.command == "clean":
        cmd_clean(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
