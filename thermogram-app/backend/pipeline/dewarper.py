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
        Detect horizontal lines using Adaptive Threshold + Morphological Operations.

        Args:
            image: Input image

        Returns:
            List of horizontal line segments as [x1, y1, x2, y2] arrays
        """
        h, w = image.shape[:2]

        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        binary_list = []
        for block_size in [5, 7, 9, 11, 13, 15, 17]:
            for c_value in [1, 2, 3]:
                binary1 = cv2.adaptiveThreshold(
                    enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY_INV, block_size, c_value
                )
                binary2 = cv2.adaptiveThreshold(
                    enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY, block_size, c_value
                )
                binary_list.extend([binary1, binary2])

        horizontal_lines = []
        for kernel_width in [w // 50, w // 40, w // 30, w // 20, w // 15]:
            kernel_h = np.ones((1, max(5, kernel_width)), np.uint8)

            for binary in binary_list:
                horizontal_mask = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_h)
                row_sum = np.sum(horizontal_mask, axis=1)

                if np.max(row_sum) == 0:
                    continue

                window = 12
                for y in range(h):
                    start = max(0, y - window)
                    end = min(h, y + window + 1)
                    local_max = np.max(row_sum[start:end])
                    local_mean = np.mean(row_sum[start:end])

                    if row_sum[y] >= local_max * 0.9 and row_sum[y] > local_mean * 1.2:
                        horizontal_lines.append(y)

        return self._group_and_create_lines(horizontal_lines, w, group_distance=4)

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
        image: np.ndarray
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

        if len(valid_traces) < 2:
            # Fallback to simple detection
            return self._fallback_vertical_detection(image, vertical_mask)

        # Step 4: Calculate template (average shape)
        # The shape is defined by 'a' coefficient (curvature)
        avg_a = np.median([t[1][0] for t in valid_traces])
        avg_b = np.median([t[1][1] for t in valid_traces])

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

        # Step 6: Find most common spacing
        if len(merged_peaks) >= 3:
            gaps = np.diff(merged_peaks)

            # Histogram of gaps
            gap_hist = {}
            for g in gaps:
                key = int(round(g))
                if 10 <= key <= 150:
                    gap_hist[key] = gap_hist.get(key, 0) + 1

            if gap_hist:
                # Find the most frequent gap
                grid_spacing = max(gap_hist.items(), key=lambda x: x[1])[0]
            else:
                grid_spacing = int(np.median(gaps))
        else:
            grid_spacing = 32  # Fallback

        # Step 7: Find best reference point (a strong peak near center)
        center_peaks = [(x, abs(x - w/2)) for x in merged_peaks]
        center_peaks.sort(key=lambda p: p[1])
        ref_x = center_peaks[0][0] if center_peaks else w // 2

        # Step 8: Generate uniform grid with detected spacing
        all_positions = []
        x = ref_x
        while x >= 0:
            all_positions.append(int(x))
            x -= grid_spacing
        x = ref_x + grid_spacing
        while x < w:
            all_positions.append(int(x))
            x += grid_spacing
        all_positions = sorted(all_positions)

        # Step 6: Create polylines by applying template to each detected position
        polylines = []
        y_full = np.arange(0, h, 5)
        y_mid = h / 2

        for target_x in all_positions:
            # Apply template shape centered at target_x
            # x = a*y^2 + b*y + c, we want x(y_mid) = target_x
            # So: c = target_x - a*y_mid^2 - b*y_mid
            x_at_mid = avg_a * y_mid**2 + avg_b * y_mid
            x_vals = avg_a * y_full**2 + avg_b * y_full - x_at_mid + target_x

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
        mode: int = 0
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

        Returns:
            GridOverlayResult with overlay image
        """
        mode_names = {
            0: "Original",
            4: "Horizontal",
            5: "Vertical",
            6: "Combined"
        }

        try:
            # Mode 0: Original image
            if mode == 0:
                return GridOverlayResult(
                    overlay_image=image.copy(),
                    vertical_lines=0,
                    horizontal_lines=0,
                    success=True,
                    message="Original image"
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

            # Detect and draw vertical lines (modes 5 and 6)
            if mode in [5, 6]:
                vertical_polylines = self.detect_vertical_lines(image)
                v_count = len(vertical_polylines)
                overlay = self._draw_vertical_polylines(
                    overlay, vertical_polylines,
                    color=(255, 0, 0),  # Blue
                    thickness=2
                )

            return GridOverlayResult(
                overlay_image=overlay,
                vertical_lines=v_count,
                horizontal_lines=h_count,
                success=True,
                message=f"[{mode_names.get(mode, 'Unknown')}] H:{h_count} V:{v_count}"
            )

        except Exception as e:
            return GridOverlayResult(
                overlay_image=image,
                vertical_lines=0,
                horizontal_lines=0,
                success=False,
                message=f"Error creating grid overlay: {str(e)}"
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
