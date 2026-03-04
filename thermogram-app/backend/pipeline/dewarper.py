"""
Dewarper Module - Stage 2 of the thermogram processing pipeline.

Straightens curved grid lines in thermogram images using displacement mapping.
"""

import cv2
import numpy as np
import time
from dataclasses import dataclass
from typing import Tuple, List, Optional

from models import DewarpResult, GridOverlayResult, FlattenedGridResult, TimingInfo
from configs import ChartConfig, DewarpConfig, GridDetectionConfig
from utils.grid_utils import (
    cluster_lines,
    extend_lines_to_bounds,
    detect_lines_morphological,
    trace_vertical_lines,
    fit_line_curves,
    create_displacement_map,
    apply_displacement_map,
)


class Dewarper:
    """
    Dewarps thermogram images by detecting and straightening curved grid lines.

    Stage 2 of the pipeline uses vertical line tracing and polynomial fitting
    to create a displacement map that straightens the grid.
    """

    def __init__(
        self,
        config: Optional[ChartConfig] = None,
        debug: bool = False
    ):
        """
        Initialize dewarper.

        Args:
            config: Chart configuration (uses defaults if None)
            debug: Enable debug mode for intermediate images
        """
        self.config = config
        self.dewarp_config = config.dewarp if config else DewarpConfig()
        self.grid_config = config.grid_detection if config else GridDetectionConfig()
        self.debug = debug
        self.debug_images = {}
        # Detected curve coefficients (set by detect_vertical_lines)
        self._detected_curve_a = 0.0
        self._detected_curve_b = 0.0

    def dewarp(self, image: np.ndarray) -> DewarpResult:
        """
        Dewarp thermogram image by tracing vertical grid lines and straightening them.

        Algorithm:
        1. Create a binary mask of vertical lines using morphological operations
        2. Scan the mask at regular y-intervals to find x-positions of each line
        3. For each detected vertical line, compute its curve (x as function of y)
        4. Create displacement map to straighten all curves
        5. Apply remapping

        Args:
            image: Input image (BGR format)

        Returns:
            DewarpResult with straightened image and metadata
        """
        start_time = time.perf_counter()

        try:
            h, w = image.shape[:2]
            cfg = self.dewarp_config

            # Step 1: Create vertical line mask
            vertical_mask = self._create_vertical_mask(image)

            if self.debug:
                self.debug_images['vertical_mask'] = vertical_mask

            # Step 2: Trace vertical lines
            line_traces = trace_vertical_lines(
                vertical_mask,
                num_samples=cfg.num_y_samples,
                min_line_spacing=cfg.min_line_spacing
            )

            if len(line_traces) < 3:
                return self._create_failure_result(
                    image, start_time,
                    f"Not enough vertical lines detected: {len(line_traces)}"
                )

            # Step 3: Fit curves to lines
            line_curves = fit_line_curves(
                line_traces,
                polynomial_degree=cfg.polynomial_degree
            )

            if len(line_curves) < 3:
                return self._create_failure_result(
                    image, start_time,
                    "Failed to fit curves to lines"
                )

            # Step 4: Create displacement map
            displacement_map = create_displacement_map(
                (h, w),
                line_curves,
                max_displacement_ratio=cfg.max_displacement_ratio,
                gaussian_kernel_size=cfg.gaussian_kernel_size
            )

            if self.debug:
                self.debug_images['displacement_map'] = displacement_map

            # Step 5: Apply remapping
            straightened = apply_displacement_map(image, displacement_map)

            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000

            return DewarpResult(
                original_image=image,
                straightened_image=straightened,
                forward_transform=np.eye(3),
                inverse_transform=np.eye(3),
                grid_lines_detected=len(line_curves),
                success=True,
                message=f"Dewarping successful - {len(line_curves)} lines straightened",
                timing=TimingInfo(
                    stage_name="dewarp",
                    start_time=start_time,
                    end_time=end_time,
                    duration_ms=duration_ms
                ),
                vertical_lines_count=len(line_curves),
                displacement_map=displacement_map
            )

        except Exception as e:
            return self._create_failure_result(
                image, start_time,
                f"Error during dewarping: {str(e)}"
            )

    def _create_vertical_mask(self, image: np.ndarray) -> np.ndarray:
        """
        Create binary mask of vertical structures.

        Args:
            image: Input image

        Returns:
            Binary mask where vertical lines are white
        """
        cfg = self.grid_config

        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Enhance contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Adaptive threshold - invert so lines are white
        binary = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 15, 2
        )

        # Strong vertical morphology
        kernel_v = np.ones((cfg.vertical_kernel_height, cfg.vertical_kernel_width), np.uint8)
        vertical_mask = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_v)

        # Close small gaps
        kernel_close = np.ones((10, 1), np.uint8)
        vertical_mask = cv2.morphologyEx(vertical_mask, cv2.MORPH_CLOSE, kernel_close)

        return vertical_mask

    def _create_failure_result(
        self,
        image: np.ndarray,
        start_time: float,
        message: str
    ) -> DewarpResult:
        """Create a failure result with timing."""
        end_time = time.perf_counter()
        return DewarpResult(
            original_image=image,
            straightened_image=image,
            forward_transform=np.eye(3),
            inverse_transform=np.eye(3),
            grid_lines_detected=0,
            success=False,
            message=message,
            timing=TimingInfo(
                stage_name="dewarp",
                start_time=start_time,
                end_time=end_time,
                duration_ms=(end_time - start_time) * 1000
            )
        )

    # =========================================================================
    # Horizontal Line Detection (for grid overlay)
    # =========================================================================

    def detect_horizontal_lines(self, image: np.ndarray) -> List[np.ndarray]:
        """
        Detect horizontal lines using multiple combined approaches.

        Algorithm combines:
        1. GREEN color filter (grid lines are green)
        2. Margin exclusion (skip left/right edges with numbers)
        3. HoughLinesP for line segment detection
        4. Row projection on filtered region
        5. Expected spacing inference

        Args:
            image: Input image

        Returns:
            List of horizontal line segments as [x1, y1, x2, y2] arrays
        """
        h, w = image.shape[:2]

        # Define analysis region (exclude margins with numbers/text)
        margin_left = int(w * 0.08)   # Skip leftmost 8%
        margin_right = int(w * 0.02)  # Skip rightmost 2%
        analysis_region = image[:, margin_left:w - margin_right]
        region_w = analysis_region.shape[1]

        detected_lines = set()  # Use set to avoid duplicates

        if len(image.shape) == 3:
            # ============================================================
            # METHOD 1: Color Filter (for colored grids - green OR orange)
            # ============================================================
            hsv = cv2.cvtColor(analysis_region, cv2.COLOR_BGR2HSV)

            # Green color range (H: 35-85 covers yellow-green to green-cyan)
            lower_green = np.array([35, 40, 40])
            upper_green = np.array([85, 255, 255])
            green_mask = cv2.inRange(hsv, lower_green, upper_green)

            # Orange/Brown color range (H: 5-25 covers orange to brown)
            lower_orange = np.array([5, 50, 50])
            upper_orange = np.array([25, 255, 200])
            orange_mask = cv2.inRange(hsv, lower_orange, upper_orange)

            # Red color range (H: 0-10 and 170-180 for red hues)
            lower_red1 = np.array([0, 50, 50])
            upper_red1 = np.array([10, 255, 200])
            red_mask1 = cv2.inRange(hsv, lower_red1, upper_red1)

            lower_red2 = np.array([170, 50, 50])
            upper_red2 = np.array([180, 255, 200])
            red_mask2 = cv2.inRange(hsv, lower_red2, upper_red2)

            # Combine all grid color masks
            grid_color_mask = cv2.bitwise_or(green_mask, orange_mask)
            grid_color_mask = cv2.bitwise_or(grid_color_mask, red_mask1)
            grid_color_mask = cv2.bitwise_or(grid_color_mask, red_mask2)

            # Apply horizontal morphology
            kernel_h = np.ones((1, region_w // 15), np.uint8)
            color_horizontal = cv2.morphologyEx(grid_color_mask, cv2.MORPH_OPEN, kernel_h)

            # Close gaps
            kernel_close = np.ones((1, 20), np.uint8)
            color_horizontal = cv2.morphologyEx(color_horizontal, cv2.MORPH_CLOSE, kernel_close)

            # Row projection on color mask
            color_row_sum = np.sum(color_horizontal, axis=1).astype(np.float64)
            if np.max(color_row_sum) > 0:
                color_row_sum = color_row_sum / np.max(color_row_sum)

                # Find peaks
                for y in range(5, h - 5):
                    if color_row_sum[y] > 0.3:  # 30% threshold
                        window = color_row_sum[max(0, y-5):min(h, y+6)]
                        if color_row_sum[y] >= np.max(window) * 0.95:
                            detected_lines.add(y)

            # ============================================================
            # METHOD 2: HoughLinesP on color mask
            # ============================================================
            edges = cv2.Canny(grid_color_mask, 50, 150)
            lines = cv2.HoughLinesP(
                edges,
                rho=1,
                theta=np.pi / 180,
                threshold=50,
                minLineLength=region_w // 3,  # At least 1/3 of region width
                maxLineGap=20
            )

            if lines is not None:
                for line in lines:
                    x1, y1, x2, y2 = line[0]
                    # Check if approximately horizontal (angle < 5 degrees)
                    if abs(y2 - y1) < abs(x2 - x1) * 0.087:  # tan(5°) ≈ 0.087
                        y_avg = (y1 + y2) // 2
                        detected_lines.add(y_avg)

            gray = cv2.cvtColor(analysis_region, cv2.COLOR_BGR2GRAY)
        else:
            gray = analysis_region.copy()

        # ============================================================
        # METHOD 3: Intensity-based detection (primary for faded grids)
        # ============================================================
        # Very aggressive contrast enhancement for faded images
        clahe = cv2.createCLAHE(clipLimit=5.0, tileGridSize=(4, 4))
        enhanced = clahe.apply(gray)

        # Multiple adaptive threshold parameters for robustness
        binary_combined = np.zeros_like(gray)
        for block_size in [7, 11, 15, 21]:
            for c_val in [1, 2, 3, 4]:
                binary = cv2.adaptiveThreshold(
                    enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY_INV, block_size, c_val
                )
                binary_combined = cv2.bitwise_or(binary_combined, binary)

        # Also try Sobel gradient for edge detection
        sobel_x = cv2.Sobel(enhanced, cv2.CV_64F, 0, 1, ksize=3)
        sobel_abs = np.abs(sobel_x)
        sobel_norm = (sobel_abs / sobel_abs.max() * 255).astype(np.uint8)
        _, sobel_binary = cv2.threshold(sobel_norm, 30, 255, cv2.THRESH_BINARY)
        binary_combined = cv2.bitwise_or(binary_combined, sobel_binary)

        # Horizontal morphology (narrower kernel for finer lines)
        kernel_h = np.ones((1, region_w // 30), np.uint8)
        horizontal_mask = cv2.morphologyEx(binary_combined, cv2.MORPH_OPEN, kernel_h)

        # Row projection
        row_sum = np.sum(horizontal_mask, axis=1).astype(np.float64)
        if np.max(row_sum) > 0:
            row_sum = row_sum / np.max(row_sum)

            for y in range(5, h - 5):
                if row_sum[y] > 0.4:  # 40% threshold
                    window = row_sum[max(0, y-5):min(h, y+6)]
                    if row_sum[y] >= np.max(window) * 0.95:
                        detected_lines.add(y)

        # ============================================================
        # METHOD 4: HoughLinesP on intensity mask
        # ============================================================
        edges_gray = cv2.Canny(horizontal_mask, 50, 150)
        lines_gray = cv2.HoughLinesP(
            edges_gray,
            rho=1,
            theta=np.pi / 180,
            threshold=30,
            minLineLength=region_w // 4,
            maxLineGap=30
        )

        if lines_gray is not None:
            for line in lines_gray:
                x1, y1, x2, y2 = line[0]
                if abs(y2 - y1) < abs(x2 - x1) * 0.087:
                    y_avg = (y1 + y2) // 2
                    detected_lines.add(y_avg)

        # ============================================================
        # POST-PROCESSING: Merge nearby lines and filter
        # ============================================================
        if not detected_lines:
            return []

        # Sort all detected y positions
        all_y = sorted(detected_lines)

        # Group nearby lines (within 10 pixels) - compare to group start
        min_line_spacing = 10
        grouped = []
        current_group = [all_y[0]]

        for y in all_y[1:]:
            # Compare to the START of the current group (not the last element)
            if y - current_group[0] <= min_line_spacing:
                current_group.append(y)
            else:
                # Take median of group
                grouped.append(int(np.median(current_group)))
                current_group = [y]

        grouped.append(int(np.median(current_group)))

        # ============================================================
        # METHOD 5: Infer missing lines using expected spacing
        # ============================================================
        if len(grouped) >= 3:
            # Calculate most common spacing
            gaps = np.diff(grouped)
            if len(gaps) > 0:
                # Find spacing that appears most frequently (within tolerance)
                gap_counts = {}
                for g in gaps:
                    # Round to nearest 5 for grouping
                    key = round(g / 5) * 5
                    if 15 <= key <= 100:  # Minimum 15px expected spacing
                        gap_counts[key] = gap_counts.get(key, 0) + 1

                if gap_counts:
                    expected_spacing = max(gap_counts.items(), key=lambda x: x[1])[0]

                    # Fill in missing lines if gap is ~2x expected spacing
                    final_lines = [grouped[0]]
                    for i in range(1, len(grouped)):
                        gap = grouped[i] - final_lines[-1]
                        if gap > expected_spacing * 1.7:
                            # Insert intermediate lines
                            num_missing = round(gap / expected_spacing) - 1
                            for j in range(1, num_missing + 1):
                                inferred_y = final_lines[-1] + int(j * gap / (num_missing + 1))
                                # Only add if not too close to existing lines
                                if all(abs(inferred_y - existing) >= min_line_spacing for existing in final_lines):
                                    final_lines.append(inferred_y)
                        final_lines.append(grouped[i])

                    grouped = sorted(final_lines)

        # Final deduplication: remove lines that are too close
        grouped = sorted(set(grouped))
        if len(grouped) > 1:
            final_grouped = [grouped[0]]
            for y in grouped[1:]:
                if y - final_grouped[-1] >= min_line_spacing:
                    final_grouped.append(y)
            grouped = final_grouped

        return [np.array([0, y, w - 1, y]) for y in grouped]

    def _group_and_create_lines(
        self,
        y_positions: List[int],
        width: int,
        group_distance: int = 10
    ) -> List[np.ndarray]:
        """Group nearby y positions and create full-width line arrays."""
        if not y_positions:
            return []

        y_positions = sorted(y_positions)
        filtered_lines = []
        current_group = [y_positions[0]]

        for y in y_positions[1:]:
            if y - current_group[-1] <= group_distance:
                current_group.append(y)
            else:
                center = int(np.mean(current_group))
                filtered_lines.append(center)
                current_group = [y]

        center = int(np.mean(current_group))
        filtered_lines.append(center)

        return [np.array([0, y, width - 1, y]) for y in filtered_lines]

    # =========================================================================
    # Vertical Line Detection (curved/cylindrical lines)
    # =========================================================================

    def detect_vertical_lines(
        self,
        image: np.ndarray,
        curvature_override: Optional[float] = None
    ) -> List[List[Tuple[int, int]]]:
        """
        Detect vertical curved lines using template-based approach.

        All vertical lines have the same shape (like left half of a circle):
        - Center (y=h/2) is the leftmost point
        - Top and bottom ends curve to the right

        Algorithm:
        1. Find strong lines from interior of image (not edges)
        2. Trace them to get the barrel distortion shape
        3. Find consistent grid spacing
        4. Generate all lines using the template shape

        Args:
            image: Input image
            curvature_override: Manual override for curvature (0.0 = straight, 1.0 = max curve)
                               If provided, skips auto-detection and uses this value.

        Returns:
            List of polylines (each polyline is list of (x, y) tuples)
        """
        h, w = image.shape[:2]

        # Step 1: Create vertical mask
        vertical_mask = self._create_vertical_mask(image)

        # Step 2: Find line candidates from INTERIOR only (exclude edges)
        margin = int(w * 0.15)  # Skip first/last 15%

        column_sum = np.sum(vertical_mask, axis=0).astype(np.float64)
        kernel = np.ones(5) / 5
        column_sum = np.convolve(column_sum, kernel, mode='same')

        # Find peaks in interior region
        threshold = np.max(column_sum[margin:w-margin]) * 0.1
        peaks = []
        for x in range(margin, w - margin):
            if column_sum[x] > threshold:
                if column_sum[x] >= np.max(column_sum[max(margin, x-8):min(w-margin, x+9)]):
                    peaks.append((x, column_sum[x]))

        # Merge nearby peaks
        merged = []
        for x, s in peaks:
            if not merged or x - merged[-1][0] >= 12:
                merged.append((x, s))
            elif s > merged[-1][1]:
                merged[-1] = (x, s)

        # Sort by strength
        merged.sort(key=lambda p: -p[1])

        # Step 3: Trace top candidates to find template shape
        num_y_samples = h // 4
        y_samples = np.linspace(0, h - 1, num_y_samples).astype(int)

        valid_traces = []  # (center_x, polynomial_coeffs, points)

        for peak_x, _ in merged[:30]:
            points = []
            current_x = peak_x

            for y in y_samples:
                x_start = max(0, current_x - 20)
                x_end = min(w, current_x + 21)
                row = vertical_mask[y, x_start:x_end]

                if np.any(row > 127):
                    indices = np.where(row > 127)[0]
                    cx = x_start + int(np.mean(indices))
                    points.append((y, cx))
                    current_x = int(0.6 * current_x + 0.4 * cx)

            # Need 60% coverage
            if len(points) < num_y_samples * 0.6:
                continue

            points = np.array(points)
            try:
                coeffs = np.polyfit(points[:, 0], points[:, 1], 2)
                a, b, c = coeffs

                # Must have POSITIVE 'a' (barrel distortion - curves right at ends)
                # and reasonable magnitude
                if a > 0.00001 and a < 0.002:
                    valid_traces.append((peak_x, coeffs, points))
            except:
                continue

        if len(valid_traces) < 2 and curvature_override is None:
            # Fallback to simple detection
            return self._fallback_vertical_detection(image, vertical_mask)

        # Step 4: Calculate template (average shape)
        # The shape is defined by coefficients: x = a*y² + b*y + c
        # 'a' = curvature intensity, 'b' = asymmetry (where bend is centered)
        detected_a = np.median([t[1][0] for t in valid_traces])
        detected_b = np.median([t[1][1] for t in valid_traces])

        # Store detected coefficients for client-side rendering
        self._detected_curve_a = float(detected_a)
        self._detected_curve_b = float(detected_b)

        if curvature_override is not None:
            # Manual override: scale the detected curvature
            # 0.0 = no curvature, 1.0 = full detected curvature, >1.0 = exaggerated
            avg_a = detected_a * curvature_override
            avg_b = detected_b * curvature_override  # Scale asymmetry proportionally
        else:
            avg_a = detected_a
            avg_b = detected_b

        # Step 5: Analyze spacing across entire image
        full_column_sum = np.sum(vertical_mask, axis=0).astype(np.float64)
        kernel = np.ones(3) / 3
        full_column_sum = np.convolve(full_column_sum, kernel, mode='same')

        # Find ALL peaks
        threshold = np.max(full_column_sum) * 0.08
        all_peaks = []
        for x in range(5, w - 5):
            if full_column_sum[x] > threshold:
                if full_column_sum[x] >= np.max(full_column_sum[max(0, x-5):min(w, x+6)]):
                    all_peaks.append(x)

        # Merge nearby peaks
        merged_peaks = []
        for x in all_peaks:
            if not merged_peaks or x - merged_peaks[-1] >= 8:
                merged_peaks.append(x)

        # Step 6: Find most common spacing (use float for precision)
        if len(merged_peaks) >= 3:
            gaps = np.diff(merged_peaks).astype(float)

            # Histogram of gaps (rounded for counting)
            gap_hist = {}
            for g in gaps:
                key = int(round(g))
                if 10 <= key <= 150:
                    gap_hist[key] = gap_hist.get(key, 0) + 1

            if gap_hist:
                # Find the most frequent gap
                most_common_key = max(gap_hist.items(), key=lambda x: x[1])[0]
                # Get precise average of gaps close to this value
                close_gaps = [g for g in gaps if abs(g - most_common_key) < 5]
                grid_spacing = np.mean(close_gaps) if close_gaps else float(most_common_key)
            else:
                grid_spacing = np.median(gaps)
        else:
            grid_spacing = 32.0  # Fallback

        # Step 7: Use multiple anchor points for better alignment
        # Find strong peaks across the image (left, center, right)
        left_peaks = [x for x in merged_peaks if x < w * 0.3]
        center_peaks = [x for x in merged_peaks if w * 0.3 <= x <= w * 0.7]
        right_peaks = [x for x in merged_peaks if x > w * 0.7]

        # Use center peak as primary reference
        if center_peaks:
            ref_x = center_peaks[len(center_peaks) // 2]
        elif merged_peaks:
            ref_x = merged_peaks[len(merged_peaks) // 2]
        else:
            ref_x = w // 2

        # Step 8: Generate grid with precise spacing (float arithmetic)
        all_positions = []
        x = float(ref_x)
        while x >= 0:
            all_positions.append(int(round(x)))
            x -= grid_spacing
        x = float(ref_x) + grid_spacing
        while x < w:
            all_positions.append(int(round(x)))
            x += grid_spacing
        all_positions = sorted(all_positions)

        # Step 6: Create polylines by applying template to each detected position
        polylines = []
        y_full = np.arange(0, h, 5)
        y_mid = h / 2

        for target_x in all_positions:
            # Apply template shape centered at y_mid (symmetric curve)
            # Formula: x = a * (y - y_mid)^2 + target_x
            # This ensures:
            # - At y = y_mid (center): x = target_x (fixed point)
            # - At y = 0 (top): x = a * y_mid^2 + target_x
            # - At y = h (bottom): x = a * y_mid^2 + target_x (same as top!)
            x_vals = avg_a * (y_full - y_mid)**2 + target_x

            x_vals = np.clip(x_vals, 0, w - 1)
            polyline = [(int(x), int(y)) for y, x in zip(y_full, x_vals)]
            polylines.append(polyline)

        return polylines

    def _fallback_vertical_detection(
        self,
        image: np.ndarray,
        vertical_mask: np.ndarray
    ) -> List[List[Tuple[int, int]]]:
        """Fallback detection when template approach fails."""
        h, w = image.shape[:2]

        column_sum = np.sum(vertical_mask, axis=0).astype(np.float64)
        threshold = np.max(column_sum) * 0.1

        peaks = []
        for x in range(10, w - 10):
            if column_sum[x] > threshold:
                if column_sum[x] >= np.max(column_sum[max(0, x-10):min(w, x+11)]):
                    peaks.append(x)

        # Simple straight lines
        y_full = np.arange(0, h, 5)
        return [[(x, int(y)) for y in y_full] for x in peaks[:100]]

    def _draw_vertical_polylines(
        self,
        image: np.ndarray,
        polylines: List[List[Tuple[int, int]]],
        color: Tuple[int, int, int] = (255, 0, 0),  # Blue in BGR
        thickness: int = 2
    ) -> np.ndarray:
        """
        Draw curved vertical lines as polylines on image.

        Args:
            image: Image to draw on
            polylines: List of polylines from detect_vertical_lines
            color: BGR color tuple
            thickness: Line thickness

        Returns:
            Image with polylines drawn
        """
        result = image.copy()

        for polyline in polylines:
            if len(polyline) >= 2:
                pts = np.array(polyline, dtype=np.int32)
                cv2.polylines(result, [pts], isClosed=False, color=color, thickness=thickness)

        return result

    # =========================================================================
    # Grid Overlay Methods
    # =========================================================================

    def create_grid_overlay(
        self,
        image: np.ndarray,
        mode: int = 0,
        curvature_override: Optional[float] = None
    ) -> GridOverlayResult:
        """
        Create an overlay showing detected grid lines.

        Args:
            image: Input image
            mode: View mode
                0 = Original image (no overlay)
                4 = Horizontal lines only (green)
                5 = Vertical lines only (blue)
                6 = Both horizontal + vertical (green + blue)
            curvature_override: Manual curvature for vertical lines (0.0=straight, 1.0=max curve)

        Returns:
            GridOverlayResult with overlay image
        """
        mode_names = {
            0: "Original",
            4: "Horizontal",
            5: "Vertical",
            6: "Combined"
        }

        h, w = image.shape[:2]
        v_line_positions = []
        h_line_positions = []

        try:
            # Mode 0: Original image
            if mode == 0:
                return GridOverlayResult(
                    overlay_image=image.copy(),
                    vertical_lines=0,
                    horizontal_lines=0,
                    success=True,
                    message="Original image",
                    image_height=h,
                    image_width=w
                )

            overlay = image.copy()
            h_count = 0
            v_count = 0

            # Detect and draw horizontal lines (modes 4 and 6)
            if mode in [4, 6]:
                horizontal_lines = self.detect_horizontal_lines(image)
                h_count = len(horizontal_lines)
                for line in horizontal_lines:
                    x1, y1, x2, y2 = line
                    cv2.line(overlay, (x1, y1), (x2, y2), (0, 255, 0), 2)  # Green
                    # Store Y position (average of y1 and y2)
                    h_line_positions.append((y1 + y2) // 2)

            # Detect and draw vertical lines (modes 5 and 6)
            if mode in [5, 6]:
                vertical_polylines = self.detect_vertical_lines(image, curvature_override=curvature_override)
                v_count = len(vertical_polylines)
                overlay = self._draw_vertical_polylines(
                    overlay, vertical_polylines,
                    color=(255, 0, 0),  # Blue
                    thickness=2
                )
                # Extract X positions at y_mid (center of image) from polylines
                y_mid = h // 2
                for polyline in vertical_polylines:
                    # Find the point closest to y_mid
                    mid_point = min(polyline, key=lambda p: abs(p[1] - y_mid))
                    v_line_positions.append(mid_point[0])

            return GridOverlayResult(
                overlay_image=overlay,
                vertical_lines=v_count,
                horizontal_lines=h_count,
                success=True,
                message=f"[{mode_names.get(mode, 'Unknown')}] H:{h_count} V:{v_count}",
                vertical_line_positions=sorted(v_line_positions),
                horizontal_line_positions=sorted(h_line_positions),
                image_height=h,
                image_width=w,
                curve_coeff_a=self._detected_curve_a,
                curve_coeff_b=self._detected_curve_b
            )

        except Exception as e:
            return GridOverlayResult(
                overlay_image=image,
                vertical_lines=0,
                horizontal_lines=0,
                success=False,
                message=f"Error creating grid overlay: {str(e)}",
                image_height=h,
                image_width=w
            )

    def create_flattened_grid(self, image: np.ndarray) -> FlattenedGridResult:
        """
        Create an image showing only the detected horizontal grid lines.

        Args:
            image: Input image

        Returns:
            FlattenedGridResult with grid-only image
        """
        try:
            h, w = image.shape[:2]
            horizontal_lines = self.detect_horizontal_lines(image)

            flattened = np.ones((h, w, 3), dtype=np.uint8) * 255

            for line in horizontal_lines:
                y = line[1]
                cv2.line(flattened, (0, y), (w-1, y), (0, 255, 0), 1)

            return FlattenedGridResult(
                flattened_image=flattened,
                vertical_lines=0,
                horizontal_lines=len(horizontal_lines),
                success=True,
                message=f"Flattened grid with {len(horizontal_lines)} horizontal lines"
            )

        except Exception as e:
            h, w = image.shape[:2]
            return FlattenedGridResult(
                flattened_image=np.ones((h, w, 3), dtype=np.uint8) * 255,
                vertical_lines=0,
                horizontal_lines=0,
                success=False,
                message=f"Error creating flattened grid: {str(e)}"
            )

    def create_straightened_image(self, image: np.ndarray) -> FlattenedGridResult:
        """
        Returns the dewarped/straightened image only.

        Args:
            image: Input image

        Returns:
            FlattenedGridResult with straightened image
        """
        try:
            dewarp_result = self.dewarp(image)

            if not dewarp_result.success:
                return FlattenedGridResult(
                    flattened_image=image,
                    vertical_lines=0,
                    horizontal_lines=0,
                    success=False,
                    message=f"Dewarping failed: {dewarp_result.message}"
                )

            return FlattenedGridResult(
                flattened_image=dewarp_result.straightened_image,
                vertical_lines=dewarp_result.grid_lines_detected,
                horizontal_lines=0,
                success=True,
                message="Straightened image created successfully"
            )

        except Exception as e:
            return FlattenedGridResult(
                flattened_image=image,
                vertical_lines=0,
                horizontal_lines=0,
                success=False,
                message=f"Error creating straightened image: {str(e)}"
            )


def dewarp_image(
    image_path: str,
    output_path: str = None,
    config: Optional[ChartConfig] = None
) -> DewarpResult:
    """
    Convenience function to dewarp an image file.

    Args:
        image_path: Path to input image
        output_path: Path to save output (optional)
        config: Chart configuration (optional)

    Returns:
        DewarpResult
    """
    from utils.image_utils import load_image, save_image

    image = load_image(image_path)
    dewarper = Dewarper(config=config, debug=False)
    result = dewarper.dewarp(image)

    if output_path and result.success:
        save_image(result.straightened_image, output_path)

    return result


__all__ = [
    'Dewarper',
    'DewarpResult',
    'GridOverlayResult',
    'FlattenedGridResult',
    'dewarp_image',
]
