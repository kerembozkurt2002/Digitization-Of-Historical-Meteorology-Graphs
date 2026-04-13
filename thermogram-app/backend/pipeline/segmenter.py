"""
Curve Segmenter Module

Extracts the ink trace (temperature curve) from thermogram images using
a dynamic-programming (Viterbi) shortest-path approach that enforces
spatial continuity.

Pipeline:
1. Compute ink_score: (255-gray)^1.3  (saturation dropped -- analysis
   showed it provides zero discrimination for faded historical images)
   + suppress blue/purple annotations via hue penalty
2. Mask out known grid lines from calibration data
3. Horizontal Gaussian blur to stabilise column-to-column noise
4. Build cost matrix: cost = max_score - ink_score  (low = dark ink)
5. Add interpolated gravity between y_hint and y_hint_end
6. DP sweep left-to-right with bounded Y-step per column
7. Backtrack the minimum-cost path
8. Sub-pixel refinement via weighted centroid around each Y
9. Savitzky-Golay smoothing
10. Down-sample to requested interval

Optionally, if a cleaned annotation JSON exists for the image, the
annotation is loaded and used as a per-column corridor guide that
replaces the two-point gravity with a much tighter per-column target.
"""

import json
import sys
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

from scipy.signal import savgol_filter


def _dbg(msg: str) -> None:
    """Print debug message to stderr so Rust backend can capture it."""
    print(f"[segmenter] {msg}", file=sys.stderr, flush=True)


@dataclass
class CurvePoint:
    x: float
    y: float


@dataclass
class ExtractCurveResult:
    success: bool
    points: List[CurvePoint]
    num_points: int
    message: str


class CurveSegmenter:
    """Extracts the temperature curve via Viterbi DP path-finding."""

    def __init__(
        self,
        margin_ratio: float = 0.08,
        max_y_step: int = 7,
        step_penalty: float = 5.0,
        gravity_coeff: float = 0.1,
        annotation_gravity_coeff: float = 12.0,
        ink_power: float = 1.3,
        h_blur_size: int = 11,
        smooth_window: int = 31,
        smooth_polyorder: int = 3,
        subpixel_half: int = 5,
        grid_mask_band: int = 5,
        debug: bool = False,
    ):
        self.margin_ratio = margin_ratio
        self.max_y_step = max_y_step
        self.step_penalty = step_penalty
        self.gravity_coeff = gravity_coeff
        self.annotation_gravity_coeff = annotation_gravity_coeff
        self.ink_power = ink_power
        self.h_blur_size = h_blur_size
        self.smooth_window = smooth_window
        self.smooth_polyorder = smooth_polyorder
        self.subpixel_half = subpixel_half
        self.grid_mask_band = grid_mask_band
        self.debug = debug

    @staticmethod
    def _find_annotation(image_path: str) -> Optional[Path]:
        """Look for a cleaned annotation JSON for the given image."""
        img_stem = Path(image_path).stem
        ann_dir = Path(__file__).parent.parent.parent / "annotations" / "cleaned"
        candidate = ann_dir / f"{img_stem}.json"
        _dbg(f"Looking for annotation: {candidate}")
        if candidate.exists():
            _dbg(f"Found annotation: {candidate}")
            return candidate
        _dbg(f"No annotation found at {candidate}")
        return None

    @staticmethod
    def _load_annotation_guide(ann_path: Path, x0: int, x1: int, y0: int, H: int,
                               gap_threshold: int = 20) -> Optional[np.ndarray]:
        """Load annotation and return per-column Y targets in ROI coordinates.

        Returns an array of shape (W,) where W = x1-x0.  Columns covered
        by annotation data contain the guide Y value in ROI row coords;
        columns inside gaps or outside the annotation range are set to NaN
        so the caller can skip gravity for those columns.
        """
        with open(ann_path, "r") as f:
            ann = json.load(f)
        pts = ann["points"]
        if len(pts) < 2:
            _dbg(f"Annotation has only {len(pts)} points -- skipping")
            return None

        ann_x = np.array([p["x"] for p in pts])
        ann_y = np.array([p["y"] for p in pts])

        W = x1 - x0
        col_xs = np.arange(x0, x1, dtype=np.float64)

        # Split annotation into contiguous segments (detect gaps)
        segments = []
        seg_start = 0
        for i in range(1, len(ann_x)):
            if ann_x[i] - ann_x[i - 1] > gap_threshold:
                segments.append((seg_start, i))
                seg_start = i
        segments.append((seg_start, len(ann_x)))
        _dbg(f"Annotation has {len(segments)} segment(s), gap_threshold={gap_threshold}px")

        # Build guide with NaN for uncovered regions
        guide = np.full(W, np.nan, dtype=np.float64)

        for si, (s0, s1) in enumerate(segments):
            seg_x = ann_x[s0:s1]
            seg_y = ann_y[s0:s1]
            if len(seg_x) < 2:
                continue
            # Columns within this segment's range
            mask = (col_xs >= seg_x[0]) & (col_xs <= seg_x[-1])
            if mask.any():
                guide[mask] = np.interp(col_xs[mask], seg_x, seg_y)
                _dbg(f"  segment {si+1}: X [{seg_x[0]:.0f}, {seg_x[-1]:.0f}], {int(mask.sum())} cols covered")

        valid_count = int(np.isfinite(guide).sum())
        coverage = valid_count / W if W > 0 else 0
        _dbg(f"Total annotation coverage: {coverage:.1%} ({valid_count}/{W} cols)")
        if coverage < 0.05:
            _dbg("Coverage < 5% -- annotation guide rejected")
            return None

        # Convert to ROI row coordinates (NaN stays NaN)
        valid = np.isfinite(guide)
        guide_row = np.full_like(guide, np.nan)
        guide_row[valid] = np.clip(guide[valid] - y0, 0, H - 1)
        _dbg(f"Annotation guide loaded: {len(pts)} pts, {len(segments)} segments")
        return guide_row

    def _extract_segment(
        self,
        roi: np.ndarray,
        cost: np.ndarray,
        H: int,
        W: int,
        y0: int,
        x_offset: int,
        sample_interval: int,
    ) -> List[CurvePoint]:
        """Run Viterbi DP on a single contiguous segment and return points.

        Parameters
        ----------
        roi : ink-score ROI slice  (H, W)
        cost : cost matrix with gravity already baked in  (H, W)
        H, W : dimensions of the segment
        y0 : row offset of the ROI in the full image (for Y coord output)
        x_offset : column offset of this segment in the full image (for X coord output)
        sample_interval : down-sampling stride
        """
        if H < 4 or W < 4:
            return []

        k = self.max_y_step
        dp = np.full((H, W), np.inf, dtype=np.float64)
        parent = np.zeros((H, W), dtype=np.int32)

        dp[:, 0] = cost[:, 0]

        offsets = np.arange(-k, k + 1)
        transition_cost = np.abs(offsets).astype(np.float64) * self.step_penalty
        row_idx = np.arange(H)[:, None] + offsets
        row_idx_clipped = np.clip(row_idx, 0, H - 1)

        arange_H = np.arange(H)
        for x in range(1, W):
            neighbours = dp[row_idx_clipped, x - 1] + transition_cost
            best_local = np.argmin(neighbours, axis=1)
            best_row = row_idx_clipped[arange_H, best_local]
            dp[:, x] = cost[:, x] + neighbours[arange_H, best_local]
            parent[:, x] = best_row

        path_y = np.zeros(W, dtype=np.int32)
        path_y[W - 1] = int(np.argmin(dp[:, W - 1]))
        for x in range(W - 2, -1, -1):
            path_y[x] = parent[path_y[x + 1], x + 1]

        path_y_full = path_y.astype(np.float64) + y0

        # Sub-pixel refinement
        refined = np.empty(W, dtype=np.float64)
        half = self.subpixel_half
        for x in range(W):
            cy = path_y[x]
            lo = max(0, cy - half)
            hi = min(H, cy + half + 1)
            window = roi[lo:hi, x]
            if window.sum() > 0:
                local_ys = np.arange(lo, hi, dtype=np.float64) + y0
                refined[x] = np.average(local_ys, weights=window)
            else:
                refined[x] = path_y_full[x]

        # Savitzky-Golay smoothing
        win = min(self.smooth_window, len(refined))
        if win % 2 == 0:
            win -= 1
        if win >= 5 and len(refined) >= win:
            smoothed = savgol_filter(refined, window_length=win, polyorder=self.smooth_polyorder)
        else:
            smoothed = refined

        # Down-sample
        points: List[CurvePoint] = []
        for x in range(0, W, sample_interval):
            points.append(CurvePoint(x=float(x + x_offset), y=float(smoothed[x])))

        return points

    @staticmethod
    def _find_guide_segments(ann_guide: np.ndarray, min_segment_cols: int = 20) -> List[tuple]:
        """Identify contiguous non-NaN regions in the annotation guide.

        Returns a list of (col_start, col_end) tuples in ROI-local column
        indices.  Segments shorter than *min_segment_cols* are dropped.
        """
        valid = np.isfinite(ann_guide)
        segments: List[tuple] = []
        in_seg = False
        seg_start = 0
        for i in range(len(valid)):
            if valid[i] and not in_seg:
                seg_start = i
                in_seg = True
            elif not valid[i] and in_seg:
                if i - seg_start >= min_segment_cols:
                    segments.append((seg_start, i))
                in_seg = False
        if in_seg and len(valid) - seg_start >= min_segment_cols:
            segments.append((seg_start, len(valid)))
        return segments

    def extract(
        self,
        image: np.ndarray,
        calibration: Optional[Dict] = None,
        sample_interval: int = 5,
        x_min: Optional[int] = None,
        x_max: Optional[int] = None,
        y_hint: Optional[int] = None,
        y_hint_end: Optional[int] = None,
        image_path: Optional[str] = None,
        y_min: Optional[int] = None,
        y_max: Optional[int] = None,
    ) -> ExtractCurveResult:
        h, w = image.shape[:2]

        x0 = max(int(x_min), 0) if x_min is not None else 0
        x1 = min(int(x_max), w) if x_max is not None else w
        if x1 <= x0 + 20:
            return ExtractCurveResult(False, [], 0, "X range too narrow")

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        hue = hsv[:, :, 0]
        sat = hsv[:, :, 1]

        inv_gray = (255 - gray).astype(np.float32)
        ink_score = np.power(inv_gray, self.ink_power)

        annot_mask = ((hue >= 90) & (hue <= 145)) & (sat > 40)
        ink_score[annot_mask] *= 0.15

        band = self.grid_mask_band
        if calibration is not None:
            for yp in calibration.get('horizontal', {}).get('line_positions', []):
                y_lo = max(0, int(yp) - band)
                y_hi = min(h, int(yp) + band + 1)
                ink_score[y_lo:y_hi, :] = 0
            for xp in calibration.get('vertical', {}).get('line_positions', []):
                x_lo = max(0, int(xp) - band)
                x_hi = min(w, int(xp) + band + 1)
                ink_score[:, x_lo:x_hi] = 0

        if self.h_blur_size > 1:
            ink_score = cv2.GaussianBlur(ink_score, (self.h_blur_size, 1), 0)

        margin = int(h * self.margin_ratio)
        y0 = max(margin, 1)
        y1 = h - margin
        if calibration is not None:
            h_positions = calibration.get('horizontal', {}).get('line_positions', [])
            if len(h_positions) >= 2:
                cal_y0 = max(0, int(min(h_positions)) - 20)
                cal_y1 = min(h, int(max(h_positions)) + 20)
                y0 = max(y0, cal_y0)
                y1 = min(y1, cal_y1)
        if y_min is not None:
            y0 = max(y0, int(y_min))
        if y_max is not None:
            y1 = min(y1, int(y_max))
        _dbg(f"ROI: x=[{x0},{x1}], y=[{y0},{y1}]")
        roi = ink_score[y0:y1, x0:x1]
        H, W = roi.shape

        if H < 10 or W < 10:
            return ExtractCurveResult(False, [], 0, "Image too small after margins")

        cost = (float(roi.max()) - roi).astype(np.float64)

        # --- Gravity & multi-segment handling ---
        ann_guide = None
        if image_path:
            ann_path = self._find_annotation(image_path)
            if ann_path is not None:
                ann_guide = self._load_annotation_guide(ann_path, x0, x1, y0, H)
        else:
            _dbg("No image_path provided -- skipping annotation lookup")

        if ann_guide is not None:
            guide_segments = self._find_guide_segments(ann_guide)
            _dbg(f"Guide has {len(guide_segments)} contiguous segment(s)")

            if len(guide_segments) >= 2:
                # Multi-segment: run independent DP per segment
                all_points: List[CurvePoint] = []
                for si, (c0, c1) in enumerate(guide_segments):
                    seg_W = c1 - c0
                    seg_roi = roi[:, c0:c1]
                    seg_cost = cost[:, c0:c1].copy()

                    # Apply annotation gravity for this segment
                    seg_guide = ann_guide[c0:c1]
                    rows = np.arange(H, dtype=np.float64)
                    seg_gravity = np.abs(rows[:, None] - seg_guide[None, :]) * self.annotation_gravity_coeff
                    seg_cost = seg_cost + seg_gravity

                    seg_x_offset = x0 + c0
                    _dbg(f"  segment {si+1}: cols [{c0}, {c1}), X [{seg_x_offset}, {seg_x_offset + seg_W}), "
                         f"{seg_W} cols")
                    seg_pts = self._extract_segment(seg_roi, seg_cost, H, seg_W, y0, seg_x_offset, sample_interval)
                    all_points.extend(seg_pts)

                if len(all_points) < 2:
                    return ExtractCurveResult(False, [], 0, "Could not extract enough curve points")

                return ExtractCurveResult(
                    success=True,
                    points=all_points,
                    num_points=len(all_points),
                    message=f"Extracted {len(all_points)} curve points across {len(guide_segments)} segments",
                )

            # Single annotation segment: apply gravity to full cost and fall through
            valid_mask = np.isfinite(ann_guide)
            n_valid = int(valid_mask.sum())
            _dbg(f"Using single annotation segment with gravity_coeff={self.annotation_gravity_coeff}, "
                 f"{n_valid}/{W} cols covered")
            rows = np.arange(H, dtype=np.float64)
            safe_guide = np.where(valid_mask, ann_guide, 0.0)
            raw_gravity = np.abs(rows[:, None] - safe_guide[None, :]) * self.annotation_gravity_coeff
            raw_gravity[:, ~valid_mask] = 0.0
            cost = cost + raw_gravity

        elif y_hint is not None and y_hint_end is not None:
            hint_row_start = max(0, min(H - 1, y_hint - y0))
            hint_row_end = max(0, min(H - 1, y_hint_end - y0))
            guide = np.linspace(hint_row_start, hint_row_end, W)
            rows = np.arange(H, dtype=np.float64)
            gravity = np.abs(rows[:, None] - guide[None, :]) * self.gravity_coeff
            cost = cost + gravity
        elif y_hint is not None:
            hint_row = max(0, min(H - 1, y_hint - y0))
            gravity = np.abs(np.arange(H) - hint_row).astype(np.float64) * self.gravity_coeff
            cost = cost + gravity[:, None]

        # Single-segment extraction (no annotation, single annotation segment,
        # or two-point/single-point gravity)
        points = self._extract_segment(roi, cost, H, W, y0, x0, sample_interval)

        if len(points) < 2:
            return ExtractCurveResult(False, [], 0, "Could not extract enough curve points")

        return ExtractCurveResult(
            success=True,
            points=points,
            num_points=len(points),
            message=f"Extracted {len(points)} curve points",
        )


def extract_curve(
    image: np.ndarray,
    calibration: Optional[Dict] = None,
    sample_interval: int = 5,
    x_min: Optional[int] = None,
    x_max: Optional[int] = None,
    y_hint: Optional[int] = None,
    y_hint_end: Optional[int] = None,
    image_path: Optional[str] = None,
    y_min: Optional[int] = None,
    y_max: Optional[int] = None,
) -> ExtractCurveResult:
    """Convenience function to extract the curve from an image."""
    segmenter = CurveSegmenter()
    return segmenter.extract(
        image, calibration, sample_interval,
        x_min, x_max, y_hint, y_hint_end, image_path,
        y_min, y_max,
    )


__all__ = ["CurveSegmenter", "CurvePoint", "ExtractCurveResult", "extract_curve"]
