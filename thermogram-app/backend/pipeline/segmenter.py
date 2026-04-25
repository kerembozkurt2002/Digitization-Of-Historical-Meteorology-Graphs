"""
Curve Segmenter Module — v2 (Color-based approach)

Extracts the ink trace (temperature curve) from thermogram images using
color-based filtering and iterative refinement.

Pipeline:
1. Color filter: detect dark pinkish/reddish curve pixels via RGB rules
2. Remove black pencil traces using B-G difference
3. Mask out known grid lines from calibration data
4. Per-column median to get raw Y values
5. Build coarse reference curve (wide median + Gaussian)
6. If y_hint provided, anchor reference to start at y_hint
7. Refine: limit each column to reference ±BAND, take median
8. MAD-based outlier removal
9. Final smoothing (median + Gaussian)
10. Down-sample to requested interval
"""

import sys
import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from .color_profiles import ColorProfile, get_color_profile, DEFAULT_PROFILE


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


def _moving_median(a: np.ndarray, k: int) -> np.ndarray:
    """Apply moving median filter with window size k."""
    k = k | 1  # ensure odd
    pad = k // 2
    ap = np.pad(a, (pad, pad), mode="edge")
    out = np.empty_like(a)
    for i in range(len(a)):
        out[i] = np.median(ap[i:i + k])
    return out


class CurveSegmenter:
    """Extracts the temperature curve via color-based filtering and iterative refinement."""

    def __init__(
        self,
        # Color filter params
        max_intensity: int = 245,
        min_intensity: int = 85,
        rg_diff_min: int = 22,
        rb_diff_min: int = 5,
        bg_diff_min: int = -18,
        sat_min: int = 28,
        # Refinement params
        ref_band: int = 40,
        ref_median_k: int = 151,
        ref_gauss_k: int = 81,
        ref_gauss_sigma: float = 18.0,
        # Outlier removal
        outlier_mad_factor: float = 4.0,
        outlier_min_thresh: float = 10.0,
        # Smoothing
        smooth_median_k: int = 31,
        smooth_gauss_k: int = 61,
        smooth_gauss_sigma: float = 12.0,
        # Grid masking (0 = disabled, recommended for template-based calibration)
        grid_mask_band: int = 0,
        # Gap handling
        max_gap: int = 40,
        # Max Y jump between consecutive points
        max_y_jump: int = 15,
        # Search band around y_hint (pixels above and below y_hint to search)
        y_hint_band: int = 300,
        # How often to update expected Y based on found values (columns)
        y_hint_update_interval: int = 10,
        debug: bool = False,
    ):
        self.max_intensity = max_intensity
        self.min_intensity = min_intensity
        self.rg_diff_min = rg_diff_min
        self.rb_diff_min = rb_diff_min
        self.bg_diff_min = bg_diff_min
        self.sat_min = sat_min
        self.ref_band = ref_band
        self.ref_median_k = ref_median_k
        self.ref_gauss_k = ref_gauss_k
        self.ref_gauss_sigma = ref_gauss_sigma
        self.outlier_mad_factor = outlier_mad_factor
        self.outlier_min_thresh = outlier_min_thresh
        self.smooth_median_k = smooth_median_k
        self.smooth_gauss_k = smooth_gauss_k
        self.smooth_gauss_sigma = smooth_gauss_sigma
        self.grid_mask_band = grid_mask_band
        self.max_gap = max_gap
        self.max_y_jump = max_y_jump
        self.y_hint_band = y_hint_band
        self.y_hint_update_interval = y_hint_update_interval
        self.debug = debug

    def _create_color_mask(self, image: np.ndarray, profile: Optional[ColorProfile] = None) -> np.ndarray:
        """Create binary mask for curve pixels using RGB color rules.

        Args:
            image: Input image (BGR)
            profile: Color profile for the template (uses default if None)

        Returns:
            Binary mask where 255 = curve pixel
        """
        p = profile or DEFAULT_PROFILE
        _dbg(f"Using color profile: {p.description}")

        # Convert BGR to RGB for color analysis
        img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        R = img_rgb[..., 0].astype(np.int16)
        G = img_rgb[..., 1].astype(np.int16)
        B = img_rgb[..., 2].astype(np.int16)

        maxc = np.maximum(np.maximum(R, G), B)
        minc = np.minimum(np.minimum(R, G), B)
        sat = maxc - minc

        # Standard color rule based on profile
        curve_rule = (
            (maxc <= p.max_intensity) & (maxc >= p.min_intensity) &
            (R - G >= p.rg_diff_min) & (R - G <= p.rg_diff_max) &
            (R - B >= p.rb_diff_min) &
            (B - G >= p.bg_diff_min) & (B - G <= p.bg_diff_max) &
            (sat >= p.sat_min) & (sat <= p.sat_max)
        )

        # Additional grayscale detection for faint pencil traces
        if p.use_grayscale_detection:
            gray_rule = (
                (maxc <= p.grayscale_max_intensity) &
                (sat <= p.grayscale_max_sat) &
                (maxc >= 20)  # Not pure black
            )
            curve_rule = curve_rule | gray_rule
            _dbg(f"Grayscale detection enabled (max_sat={p.grayscale_max_sat}, max_int={p.grayscale_max_intensity})")

        mask = curve_rule.astype(np.uint8) * 255
        _dbg(f"Color mask: {mask.sum() // 255} pixels (profile: {p.description})")

        return mask

    def _apply_grid_mask(self, mask: np.ndarray, calibration: Optional[Dict], h: int, w: int) -> np.ndarray:
        """Zero out grid line regions in the mask."""
        if calibration is None:
            return mask

        band = self.grid_mask_band
        result = mask.copy()

        # Horizontal grid lines
        for yp in calibration.get('horizontal', {}).get('line_positions', []):
            y_lo = max(0, int(yp) - band)
            y_hi = min(h, int(yp) + band + 1)
            result[y_lo:y_hi, :] = 0

        # Vertical grid lines
        for xp in calibration.get('vertical', {}).get('line_positions', []):
            x_lo = max(0, int(xp) - band)
            x_hi = min(w, int(xp) + band + 1)
            result[:, x_lo:x_hi] = 0

        return result

    def _compute_y_limits(
        self,
        h: int,
        calibration: Optional[Dict],
        y_min: Optional[int],
        y_max: Optional[int],
    ) -> Tuple[int, int, int, int]:
        """Compute Y limits from calibration or explicit bounds.

        Returns:
            y0, y1: expanded bounds for processing (with margin)
            y_hard_min, y_hard_max: hard bounds for clamping output (grid lines)
        """
        # Start with full image height
        y0, y1 = 0, h
        y_hard_min, y_hard_max = 0, h

        # Use calibration horizontal lines if available
        if calibration is not None:
            h_positions = calibration.get('horizontal', {}).get('line_positions', [])
            if len(h_positions) >= 2:
                # Hard bounds are the exact grid lines
                y_hard_min = int(min(h_positions))
                y_hard_max = int(max(h_positions))
                # Processing bounds have margin
                y0 = max(0, y_hard_min - 20)
                y1 = min(h, y_hard_max + 20)
                _dbg(f"Y limits from calibration: [{y0}, {y1}], hard bounds: [{y_hard_min}, {y_hard_max}]")

        # Override with explicit bounds if provided
        if y_min is not None:
            y0 = max(y0, int(y_min))
            y_hard_min = max(y_hard_min, int(y_min))
        if y_max is not None:
            y1 = min(y1, int(y_max))
            y_hard_max = min(y_hard_max, int(y_max))

        return y0, y1, y_hard_min, y_hard_max

    def _per_column_median(self, mask: np.ndarray, x0: int, x1: int, y0: int, y1: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Compute per-column median Y from mask pixels.

        Returns:
            ys_raw: array of median Y values (NaN where no pixels)
            uniq: unique column indices with data
            col_data: list of (start, end) indices into sorted arrays
        """
        W = x1 - x0
        roi_mask = mask[y0:y1, x0:x1]

        ys_raw = np.full(W, np.nan, dtype=np.float32)
        r_idx, c_idx = np.where(roi_mask > 0)

        if c_idx.size == 0:
            return ys_raw, np.array([]), []

        # Sort by column for efficient per-column processing
        order = np.argsort(c_idx, kind="stable")
        c_sorted = c_idx[order]
        r_sorted = r_idx[order]

        uniq, starts = np.unique(c_sorted, return_index=True)
        ends = np.r_[starts[1:], c_sorted.size]

        for c, s, e in zip(uniq, starts, ends):
            ys_raw[c] = np.median(r_sorted[s:e]) + y0  # Convert to image coords

        return ys_raw, uniq, list(zip(starts, ends)), r_sorted, c_sorted

    def _build_reference_curve(
        self,
        ys_raw: np.ndarray,
        W: int,
        y_hint: Optional[int] = None,
        y_hint_end: Optional[int] = None,
        anchor: bool = True,
    ) -> np.ndarray:
        """Build coarse reference curve from raw Y values.

        Args:
            ys_raw: Raw Y values per column
            W: Width (number of columns)
            y_hint: Expected Y at start (for anchoring)
            y_hint_end: Expected Y at end (for anchoring)
            anchor: If True, shift reference to match y_hint/y_hint_end

        Returns:
            Reference curve (anchored or unanchored based on anchor param)
        """
        valid = ~np.isnan(ys_raw)
        if valid.sum() < 10:
            return np.full(W, np.nan, dtype=np.float32)

        xs = np.arange(W)

        # Interpolate gaps
        ys_interp = np.interp(xs, xs[valid], ys_raw[valid])

        # Wide median filter
        ref = _moving_median(ys_interp, self.ref_median_k)

        # Gaussian smoothing
        gk = cv2.getGaussianKernel(self.ref_gauss_k, sigma=self.ref_gauss_sigma)
        ref = cv2.filter2D(ref.reshape(1, -1).astype(np.float32), -1, gk.T).ravel()

        # Anchor to y_hint at start if provided and anchoring is enabled
        if anchor and y_hint is not None:
            # Shift reference so it starts at y_hint
            current_start = ref[0]
            shift_start = y_hint - current_start

            if y_hint_end is not None:
                # Linear interpolation of shift from start to end
                current_end = ref[-1]
                shift_end = y_hint_end - current_end
                shifts = np.linspace(shift_start, shift_end, W)
                ref = ref + shifts
                _dbg(f"Reference anchored: start shift={shift_start:.1f}, end shift={shift_end:.1f}")
            else:
                # Constant shift
                ref = ref + shift_start
                _dbg(f"Reference anchored to y_hint={y_hint}, shift={shift_start:.1f}")

        return ref

    def _refine_with_reference(
        self,
        ys_raw: np.ndarray,
        ref: np.ndarray,
        r_sorted: np.ndarray,
        uniq: np.ndarray,
        col_data: List[Tuple[int, int]],
        y0: int,
    ) -> np.ndarray:
        """Refine Y values by limiting to reference ± BAND."""
        W = len(ys_raw)
        ys_refined = np.full(W, np.nan, dtype=np.float32)

        for i, c in enumerate(uniq):
            s, e = col_data[i]
            ys_col = r_sorted[s:e] + y0  # Convert to image coords
            r_ref = ref[c]

            if np.isnan(r_ref):
                continue

            near = ys_col[np.abs(ys_col - r_ref) <= self.ref_band]
            if near.size >= 1:
                ys_refined[c] = np.median(near)

        return ys_refined

    def _remove_outliers(self, ys: np.ndarray) -> np.ndarray:
        """Remove outliers using MAD (Median Absolute Deviation)."""
        valid = ~np.isnan(ys)
        if valid.sum() < 10:
            return valid

        xs = np.arange(len(ys))
        ys_fill = np.interp(xs, xs[valid], ys[valid])

        med = _moving_median(ys_fill, 41)
        dev = np.abs(ys_fill - med)
        mad = np.median(dev[valid]) + 1e-6

        outlier_thresh = max(self.outlier_min_thresh, self.outlier_mad_factor * mad)
        outlier = dev > outlier_thresh

        valid_clean = valid & ~outlier
        n_removed = int(outlier.sum())
        if n_removed > 0:
            _dbg(f"Outliers removed: {n_removed}")

        return valid_clean

    def _filter_max_y_jump(self, ys_smooth: np.ndarray, gap_ok: np.ndarray) -> np.ndarray:
        """Filter out points where Y jump exceeds max_y_jump.

        Returns updated gap_ok mask with large jumps marked as gaps.
        """
        result = gap_ok.copy()
        W = len(ys_smooth)

        prev_valid_x = -1
        prev_y = None

        for x in range(W):
            if not result[x]:
                continue

            y = ys_smooth[x]

            if prev_y is not None:
                # Check jump from previous valid point
                jump = abs(y - prev_y)
                # Scale max jump by distance (allow more jump if there's a gap)
                x_dist = x - prev_valid_x
                allowed_jump = self.max_y_jump * max(1, x_dist / 5)

                if jump > allowed_jump:
                    # Large jump - mark as gap
                    result[x] = False
                    continue

            prev_valid_x = x
            prev_y = y

        n_filtered = int(gap_ok.sum() - result.sum())
        if n_filtered > 0:
            _dbg(f"Max Y jump filter removed: {n_filtered} points")

        return result

    def _smooth_curve(self, ys: np.ndarray, valid: np.ndarray) -> np.ndarray:
        """Apply final smoothing (median + Gaussian)."""
        xs = np.arange(len(ys))

        # Interpolate valid points
        if valid.sum() < 2:
            return ys

        ys_interp = np.interp(xs, xs[valid], ys[valid])

        # Moving median
        ys_smooth = _moving_median(ys_interp, self.smooth_median_k)

        # Gaussian smoothing
        gk = cv2.getGaussianKernel(self.smooth_gauss_k, sigma=self.smooth_gauss_sigma)
        ys_smooth = cv2.filter2D(ys_smooth.reshape(1, -1).astype(np.float32), -1, gk.T).ravel()

        return ys_smooth

    def _find_valid_range(self, valid: np.ndarray) -> Tuple[int, int]:
        """Find first and last valid indices."""
        valid_idx = np.where(valid)[0]
        if len(valid_idx) == 0:
            return 0, 0
        return int(valid_idx.min()), int(valid_idx.max())

    def _get_vertical_line_x_at_y(
        self,
        line_x_ref: float,
        y: float,
        curve_coeff_a: float,
        curve_center_y: float,
    ) -> float:
        """Calculate x position of a vertical line at a given y.

        Vertical lines follow: x = x_ref + a * (y - center_y)^2
        """
        dy = y - curve_center_y
        return line_x_ref + curve_coeff_a * dy * dy

    def _filter_to_grid_bounds(
        self,
        points: List[CurvePoint],
        calibration: Optional[Dict],
    ) -> List[CurvePoint]:
        """Filter points to only those within vertical grid boundaries.

        Since vertical lines are curved, the valid X range depends on each point's Y.
        """
        if calibration is None:
            _dbg("No calibration - skipping grid bounds filter")
            return points

        derived = calibration.get('derived', {})
        line_positions = derived.get('line_positions', [])
        curve_coeff_a = derived.get('curve_coeff_a', 0.0)
        curve_center_y = derived.get('curve_center_y', 0.0)

        _dbg(f"Grid filter: {len(line_positions)} lines, coeff_a={curve_coeff_a:.6f}, center_y={curve_center_y:.1f}")

        if len(line_positions) < 2:
            _dbg("Not enough line positions - skipping grid bounds filter")
            return points

        # Get first and last vertical line reference positions
        first_line_x_ref = min(line_positions)
        last_line_x_ref = max(line_positions)
        _dbg(f"Line X refs: first={first_line_x_ref:.1f}, last={last_line_x_ref:.1f}")

        # Debug: show bounds at a sample point
        if len(points) > 0:
            sample_y = points[len(points) // 2].y
            sample_x_min = self._get_vertical_line_x_at_y(first_line_x_ref, sample_y, curve_coeff_a, curve_center_y)
            sample_x_max = self._get_vertical_line_x_at_y(last_line_x_ref, sample_y, curve_coeff_a, curve_center_y)
            _dbg(f"At y={sample_y:.0f}: x bounds [{sample_x_min:.1f}, {sample_x_max:.1f}]")
            _dbg(f"Sample point x={points[len(points) // 2].x:.1f}")

        filtered: List[CurvePoint] = []
        for p in points:
            # Calculate actual x bounds at this point's y
            x_min_at_y = self._get_vertical_line_x_at_y(
                first_line_x_ref, p.y, curve_coeff_a, curve_center_y
            )
            x_max_at_y = self._get_vertical_line_x_at_y(
                last_line_x_ref, p.y, curve_coeff_a, curve_center_y
            )

            # Keep point only if within bounds
            if x_min_at_y <= p.x <= x_max_at_y:
                filtered.append(p)

        n_filtered = len(points) - len(filtered)
        if n_filtered > 0:
            _dbg(f"Filtered {n_filtered} points outside grid bounds")

        return filtered

    def _compute_gap_mask(self, valid: np.ndarray, first_x: int, last_x: int) -> np.ndarray:
        """Compute mask for columns within acceptable gap distance from valid data."""
        W = len(valid)
        valid_idx = np.where(valid)[0]

        if len(valid_idx) == 0:
            return np.zeros(W, dtype=bool)

        gap_ok = np.zeros(W, dtype=bool)
        for x in range(first_x, last_x + 1):
            pos = np.searchsorted(valid_idx, x)
            left = valid_idx[pos - 1] if pos > 0 else valid_idx[0]
            right = valid_idx[pos] if pos < len(valid_idx) else valid_idx[-1]
            gap_ok[x] = min(abs(x - left), abs(x - right)) <= self.max_gap

        return gap_ok

    def extract(
        self,
        image: np.ndarray,
        calibration: Optional[Dict] = None,
        sample_interval: int = 5,
        x_min: Optional[int] = None,
        x_max: Optional[int] = None,
        y_hint: Optional[int] = None,
        y_hint_end: Optional[int] = None,
        image_path: Optional[str] = None,  # kept for API compatibility
        y_min: Optional[int] = None,
        y_max: Optional[int] = None,
        template_id: Optional[str] = None,
    ) -> ExtractCurveResult:
        h, w = image.shape[:2]
        _dbg(f"Image size: {w}x{h}")

        # X bounds - use provided values, or fall back to grid line positions from calibration
        if x_min is not None:
            x0 = max(int(x_min), 0)
        elif calibration is not None:
            # No x_min provided - use first vertical grid line
            line_positions = calibration.get('derived', {}).get('line_positions', [])
            if line_positions:
                x0 = max(int(min(line_positions)) - 10, 0)  # Small margin
                _dbg(f"Using first grid line as x_min: {x0}")
            else:
                x0 = 0
        else:
            x0 = 0

        if x_max is not None:
            x1 = min(int(x_max), w)
        elif calibration is not None:
            # No x_max provided - use last vertical grid line
            line_positions = calibration.get('derived', {}).get('line_positions', [])
            if line_positions:
                x1 = min(int(max(line_positions)) + 10, w)  # Small margin
                _dbg(f"Using last grid line as x_max: {x1}")
            else:
                x1 = w
        else:
            x1 = w

        W = x1 - x0

        if W < 50:
            return ExtractCurveResult(False, [], 0, "X range too narrow")

        # Y bounds from calibration
        y0, y1, y_hard_min, y_hard_max = self._compute_y_limits(h, calibration, y_min, y_max)
        _dbg(f"Bounds: X=[{x0}, {x1}], Y=[{y0}, {y1}], hard Y=[{y_hard_min}, {y_hard_max}]")
        _dbg(f"y_hint={y_hint}, y_hint_end={y_hint_end}, template_id={template_id}")

        # Step 1: Create color mask using template-specific color profile
        color_profile = get_color_profile(template_id)
        mask = self._create_color_mask(image, color_profile)

        # Step 2: Apply Y limits
        mask[:y0, :] = 0
        mask[y1:, :] = 0

        # Step 3: Apply grid masking
        mask = self._apply_grid_mask(mask, calibration, h, w)

        # Step 4: Small morphological closing to connect tiny gaps
        k_tiny = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 1))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k_tiny, iterations=1)

        # Step 4b: Apply adaptive search band (sliding window that follows the curve)
        # Works with or without y_hint - if no y_hint, auto-detect from first column with pixels
        band = self.y_hint_band
        update_interval = self.y_hint_update_interval
        tight_band = 5  # Prioritize pixels within ±5px of expected_y

        # Initialize expected_y from y_hint, or auto-detect from first curve pixels
        if y_hint is not None:
            expected_y = float(y_hint)
        else:
            # Auto-detect: find median Y of first column that has curve pixels
            expected_y = None
            for col_idx in range(W):
                abs_col = x0 + col_idx
                col_pixels = np.where(mask[:, abs_col] > 0)[0]
                if len(col_pixels) > 0:
                    expected_y = float(np.median(col_pixels))
                    _dbg(f"Auto-detected initial Y from column {col_idx}: {expected_y:.0f}")
                    break
            if expected_y is None:
                expected_y = h / 2  # Fallback to center
                _dbg(f"No curve pixels found, using center Y: {expected_y:.0f}")

        recent_ys: List[float] = []

        # If y_hint_end is provided, use it to bias expected_y towards the target
        use_target_bias = y_hint is not None and y_hint_end is not None and W > 1
        if use_target_bias:
            target_slope = (y_hint_end - y_hint) / W

        for col_idx in range(W):
            abs_col = x0 + col_idx

            # If using target bias, blend expected_y with interpolated target
            if use_target_bias:
                target_y = y_hint + target_slope * col_idx
                # Blend: 70% from tracking, 30% from linear target
                if len(recent_ys) >= 5:
                    expected_y = 0.7 * np.median(recent_ys) + 0.3 * target_y
                else:
                    expected_y = target_y

            # Apply band around current expected Y
            yc = int(expected_y)
            y_lo = max(0, yc - band)
            y_hi = min(h, yc + band)

            # Zero out pixels outside the band for this column
            mask[:y_lo, abs_col] = 0
            mask[y_hi:, abs_col] = 0

            # Find pixels in band, prioritize those within ±tight_band of expected_y
            col_pixels = np.where(mask[y_lo:y_hi, abs_col] > 0)[0]
            if len(col_pixels) > 0:
                # Convert to absolute Y coordinates
                abs_ys = col_pixels + y_lo

                # Check if there are pixels within ±tight_band of expected_y
                near_expected = abs_ys[np.abs(abs_ys - expected_y) <= tight_band]

                if len(near_expected) > 0:
                    # Use ONLY the pixels near expected_y, ignore the rest
                    found_y = float(np.median(near_expected))
                    # Zero out pixels outside this tight band
                    tight_lo = max(0, int(found_y) - tight_band)
                    tight_hi = min(h, int(found_y) + tight_band + 1)
                    mask[:tight_lo, abs_col] = 0
                    mask[tight_hi:, abs_col] = 0
                else:
                    # No pixels near expected_y, use closest one
                    closest_idx = np.argmin(np.abs(abs_ys - expected_y))
                    found_y = float(abs_ys[closest_idx])

                # Enforce max_y_jump: don't allow jumps larger than max_y_jump from expected_y
                if abs(found_y - expected_y) > self.max_y_jump:
                    # Clamp to max allowed jump
                    if found_y > expected_y:
                        found_y = expected_y + self.max_y_jump
                    else:
                        found_y = expected_y - self.max_y_jump

                recent_ys.append(found_y)
                # Keep only recent values
                if len(recent_ys) > update_interval:
                    recent_ys.pop(0)
                # Update expected Y based on recent median
                if len(recent_ys) >= 3:
                    expected_y = np.median(recent_ys)

        _dbg(f"Applied adaptive search band: start={y_hint or 'auto'}, end_expected={expected_y:.0f}, band=±{band}, tight=±{tight_band}")

        # Step 5: Per-column median (Stage 1)
        result = self._per_column_median(mask, x0, x1, y0, y1)
        ys_raw, uniq, col_data = result[0], result[1], result[2]
        r_sorted = result[3] if len(result) > 3 else np.array([])
        # c_sorted = result[4] if len(result) > 4 else np.array([])

        valid0 = ~np.isnan(ys_raw)
        n_valid0 = int(valid0.sum())
        _dbg(f"Stage 1 columns: {n_valid0}/{W} ({100 * n_valid0 / W:.1f}%)")

        if n_valid0 < 50:
            return ExtractCurveResult(False, [], 0, f"Insufficient curve pixels: {n_valid0}")

        # Step 6: Build reference curve (UNANCHORED for refinement)
        # We use unanchored reference for pixel selection to avoid filtering
        # out pixels when y_hint shift is larger than ref_band
        ref_unanchored = self._build_reference_curve(ys_raw, W, anchor=False)
        _dbg(f"Reference curve (unanchored): Y range [{np.nanmin(ref_unanchored):.0f}, {np.nanmax(ref_unanchored):.0f}]")

        # Step 7: Refine with reference band (Stage 3) using UNANCHORED reference
        if len(uniq) > 0 and len(r_sorted) > 0:
            ys_refined = self._refine_with_reference(ys_raw, ref_unanchored, r_sorted, uniq, col_data, y0)
        else:
            ys_refined = ys_raw

        valid = ~np.isnan(ys_refined)
        n_valid = int(valid.sum())
        _dbg(f"Stage 3 columns: {n_valid}/{W} ({100 * n_valid / W:.1f}%)")

        if n_valid < 50:
            return ExtractCurveResult(False, [], 0, f"Insufficient refined data: {n_valid}")

        # Step 8: Outlier removal
        valid_clean = self._remove_outliers(ys_refined)
        n_clean = int(valid_clean.sum())
        _dbg(f"After outlier removal: {n_clean}/{W}")

        if n_clean < 20:
            return ExtractCurveResult(False, [], 0, f"Too few points after outlier removal: {n_clean}")

        # Step 9: Find valid range and gap mask
        first_x, last_x = self._find_valid_range(valid_clean)
        gap_ok = self._compute_gap_mask(valid_clean, first_x, last_x)

        # Step 10: Final smoothing
        ys_smooth = self._smooth_curve(ys_refined, valid_clean)

        # Step 11: (Removed) - Anchoring is no longer needed since adaptive y_hint band
        # already constrains the search to the correct area. The curve found is already
        # in the right position, no shifting required.

        # Step 12: Clamp to hard Y bounds (grid lines)
        ys_smooth = np.clip(ys_smooth, y_hard_min, y_hard_max)

        # Step 13: Apply max Y jump filter
        gap_ok = self._filter_max_y_jump(ys_smooth, gap_ok)

        # Step 14: Generate output points
        points: List[CurvePoint] = []
        for x in range(0, W, sample_interval):
            if gap_ok[x]:
                y = float(ys_smooth[x])
                # Y is already clamped, just verify it's valid
                if y_hard_min <= y <= y_hard_max:
                    points.append(CurvePoint(x=float(x + x0), y=y))

        if len(points) < 2:
            return ExtractCurveResult(False, [], 0, "Could not extract enough curve points")

        # Step 15: Filter points to be within vertical grid boundaries
        # NOTE: Disabled for now - the curvature coefficient from calibration is not
        # the actual parabolic coefficient but a UI slider value. The extraction
        # already respects x_min/x_max bounds from starting points.
        # TODO: Implement proper grid bounds calculation using the full formula:
        # x = base_x + line_slope * (y - line_mid_y) + curve_coeff_a * (y - curve_center_y)^2
        # points = self._filter_to_grid_bounds(points, calibration)

        _dbg(f"Extracted {len(points)} points")

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
    template_id: Optional[str] = None,
) -> ExtractCurveResult:
    """Convenience function to extract the curve from an image."""
    segmenter = CurveSegmenter()
    return segmenter.extract(
        image, calibration, sample_interval,
        x_min, x_max, y_hint, y_hint_end, image_path,
        y_min, y_max, template_id,
    )


def snap_drawing_to_curve(
    image: np.ndarray,
    drawn_points: List[Dict],  # List of {"x": float, "y": float}
    calibration: Optional[Dict] = None,
    snap_band: int = 5,
    sample_interval: int = 5,
) -> ExtractCurveResult:
    """
    Process manually drawn points - accept them with light smoothing.

    Interpolates drawn points to regular intervals, then applies
    light smoothing to reduce hand-drawing jitter.

    Args:
        image: Input image (BGR) - not used, kept for API compatibility
        drawn_points: List of drawn points with x, y coordinates
        calibration: Optional calibration data - not used
        snap_band: Not used (kept for API compatibility)
        sample_interval: Output point spacing (default 5 = every 5 pixels)

    Returns:
        ExtractCurveResult with smoothed drawn points
    """
    if len(drawn_points) < 2:
        return ExtractCurveResult(False, [], 0, "Need at least 2 drawn points")

    _dbg(f"Processing drawn points: {len(drawn_points)} points")

    # Sort drawn points by X
    sorted_points = sorted(drawn_points, key=lambda p: p["x"])

    # Get X range
    x_min = int(sorted_points[0]["x"])
    x_max = int(sorted_points[-1]["x"])

    # Interpolate drawn Y values to get curve at regular intervals
    drawn_xs = np.array([p["x"] for p in sorted_points])
    drawn_ys = np.array([p["y"] for p in sorted_points])

    # Create Y values at regular intervals
    xs = np.arange(x_min, x_max + 1, sample_interval)
    ys = np.interp(xs, drawn_xs, drawn_ys)

    # Apply light smoothing to reduce hand-drawing jitter
    if len(ys) > 5:
        # Small moving median to remove outliers (window=5)
        ys_smooth = _moving_median(ys, 5)

        # Light Gaussian smoothing (sigma=2) for gentle curve
        kernel_size = min(11, len(ys_smooth) | 1)  # Ensure odd, max 11
        if kernel_size >= 3:
            gk = cv2.getGaussianKernel(kernel_size, sigma=2.0)
            ys_smooth = cv2.filter2D(ys_smooth.reshape(1, -1).astype(np.float32), -1, gk.T).ravel()

        _dbg(f"Applied light smoothing (median=5, gauss_sigma=2)")
    else:
        ys_smooth = ys

    # Create output points
    output_points: List[CurvePoint] = []
    for i, x in enumerate(xs):
        output_points.append(CurvePoint(x=float(x), y=float(ys_smooth[i])))

    _dbg(f"Created {len(output_points)} smoothed points from drawing")

    if len(output_points) < 2:
        return ExtractCurveResult(False, [], 0, "No valid points generated")

    return ExtractCurveResult(
        success=True,
        points=output_points,
        num_points=len(output_points),
        message=f"Accepted {len(output_points)} drawn points (smoothed)",
    )


__all__ = ["CurveSegmenter", "CurvePoint", "ExtractCurveResult", "extract_curve", "snap_drawing_to_curve"]
