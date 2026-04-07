"""
Curve Segmenter Module

Extracts the ink trace (temperature curve) from thermogram images using
a dynamic-programming (Viterbi) shortest-path approach that enforces
spatial continuity.

Pipeline:
1. Compute ink_score map: (255-gray) * (255-sat) / 255
2. Horizontal Gaussian blur to stabilise column-to-column noise
3. Build cost matrix: cost = max_score - ink_score  (low = dark ink)
4. DP sweep left-to-right with bounded Y-step per column
5. Backtrack the minimum-cost path
6. Sub-pixel refinement via weighted centroid around each Y
7. Savitzky-Golay smoothing
8. Down-sample to requested interval
"""

import cv2
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass

from scipy.signal import savgol_filter


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
        max_y_step: int = 10,
        h_blur_size: int = 11,
        smooth_window: int = 31,
        smooth_polyorder: int = 3,
        subpixel_half: int = 5,
        debug: bool = False,
    ):
        self.margin_ratio = margin_ratio
        self.max_y_step = max_y_step
        self.h_blur_size = h_blur_size
        self.smooth_window = smooth_window
        self.smooth_polyorder = smooth_polyorder
        self.subpixel_half = subpixel_half
        self.debug = debug

    def extract(
        self,
        image: np.ndarray,
        calibration: Optional[Dict] = None,
        sample_interval: int = 5,
        x_min: Optional[int] = None,
        x_max: Optional[int] = None,
    ) -> ExtractCurveResult:
        h, w = image.shape[:2]

        # Apply user-supplied horizontal bounds
        x0 = max(int(x_min), 0) if x_min is not None else 0
        x1 = min(int(x_max), w) if x_max is not None else w
        if x1 <= x0 + 20:
            return ExtractCurveResult(False, [], 0, "X range too narrow")

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        sat = hsv[:, :, 1]

        # Step 1: ink score – high where pixel is dark AND desaturated
        inv_gray = (255 - gray).astype(np.float32)
        inv_sat = (255 - sat).astype(np.float32) / 255.0
        ink_score = inv_gray * inv_sat

        # Step 2: horizontal blur to reduce column noise (keep Y precision)
        if self.h_blur_size > 1:
            ink_score = cv2.GaussianBlur(ink_score, (self.h_blur_size, 1), 0)

        # Crop to chart area (skip margins vertically, user bounds horizontally)
        margin = int(h * self.margin_ratio)
        y0 = max(margin, 1)
        y1 = h - margin
        roi = ink_score[y0:y1, x0:x1]     # shape (H, W')
        H, W = roi.shape

        if H < 10 or W < 10:
            return ExtractCurveResult(False, [], 0, "Image too small after margins")

        # Step 3: cost = max - score (low cost = dark ink)
        cost = float(roi.max()) - roi      # shape (H, W')

        # Step 4: Viterbi DP  (left → right), vectorised over rows
        k = self.max_y_step
        dp = np.full((H, W), np.inf, dtype=np.float64)
        parent = np.zeros((H, W), dtype=np.int32)

        dp[:, 0] = cost[:, 0]

        # Build a (H, 2k+1) matrix of shifted copies of the previous column
        # so we can compute min across the Y-neighbourhood in one shot.
        offsets = np.arange(-k, k + 1)              # e.g. [-3,-2,-1,0,1,2,3]
        row_idx = np.arange(H)[:, None] + offsets    # (H, 2k+1) neighbour rows
        row_idx_clipped = np.clip(row_idx, 0, H - 1)

        arange_H = np.arange(H)
        for x in range(1, W):
            neighbours = dp[row_idx_clipped, x - 1]          # (H, 2k+1)
            best_local = np.argmin(neighbours, axis=1)        # index within window
            best_row = row_idx_clipped[arange_H, best_local]  # absolute row index
            dp[:, x] = cost[:, x] + neighbours[arange_H, best_local]
            parent[:, x] = best_row

        # Step 5: backtrack
        path_y = np.zeros(W, dtype=np.int32)
        path_y[W - 1] = int(np.argmin(dp[:, W - 1]))
        for x in range(W - 2, -1, -1):
            path_y[x] = parent[path_y[x + 1], x + 1]

        # Convert back to full-image Y coordinates
        path_y_full = path_y.astype(np.float64) + y0

        # Step 6: sub-pixel refinement via weighted centroid
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

        # Step 7: Savitzky-Golay smoothing
        win = min(self.smooth_window, len(refined))
        if win % 2 == 0:
            win -= 1
        if win >= 5 and len(refined) >= win:
            smoothed = savgol_filter(refined, window_length=win, polyorder=self.smooth_polyorder)
        else:
            smoothed = refined

        # Step 8: down-sample to requested interval (output in absolute image coords)
        points: List[CurvePoint] = []
        for x in range(0, W, sample_interval):
            points.append(CurvePoint(x=float(x + x0), y=float(smoothed[x])))

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
) -> ExtractCurveResult:
    """Convenience function to extract the curve from an image."""
    segmenter = CurveSegmenter()
    return segmenter.extract(image, calibration, sample_interval, x_min, x_max)


__all__ = ["CurveSegmenter", "CurvePoint", "ExtractCurveResult", "extract_curve"]
