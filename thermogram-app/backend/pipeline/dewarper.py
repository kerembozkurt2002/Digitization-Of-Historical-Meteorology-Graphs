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

    def detect_horizontal_lines(
        self,
        image: np.ndarray,
        algorithm: int = 4
    ) -> List[np.ndarray]:
        """
        Detect horizontal lines using specified algorithm.

        Args:
            image: Input image
            algorithm: Detection algorithm (1-4)

        Returns:
            List of horizontal line segments
        """
        if algorithm == 1:
            return self._algo_canny_hough(image)
        elif algorithm == 2:
            return self._algo_vertical_gradient(image)
        elif algorithm == 3:
            return self._algo_lsd(image)
        elif algorithm == 4:
            return self._algo_adaptive_morphological(image)
        else:
            return self._algo_canny_hough(image)

    def _algo_canny_hough(self, image: np.ndarray) -> List[np.ndarray]:
        """Algorithm 1: Canny Edge Detection + Hough Transform."""
        h, w = image.shape[:2]

        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)
        edges = cv2.Canny(blurred, 20, 80, apertureSize=3)

        lines = cv2.HoughLinesP(
            edges, rho=1, theta=np.pi/180, threshold=50,
            minLineLength=w // 10, maxLineGap=30
        )

        horizontal_lines = []
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                dx = abs(x2 - x1)
                dy = abs(y2 - y1)
                if dx > 0:
                    angle = np.arctan(dy / dx) * 180 / np.pi
                    if angle < 8:
                        horizontal_lines.append((y1 + y2) // 2)

        return self._group_and_create_lines(horizontal_lines, w)

    def _algo_vertical_gradient(self, image: np.ndarray) -> List[np.ndarray]:
        """Algorithm 2: Vertical Gradient (derivative-based)."""
        h, w = image.shape[:2]

        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        grad_y = cv2.Sobel(enhanced, cv2.CV_64F, 0, 1, ksize=3)
        grad_y = np.abs(grad_y)

        row_gradient_sum = np.sum(grad_y, axis=1)
        if np.max(row_gradient_sum) > 0:
            row_gradient_sum = row_gradient_sum / np.max(row_gradient_sum)

        horizontal_lines = []
        window = 20

        for y in range(h):
            start = max(0, y - window)
            end = min(h, y + window + 1)
            local_max = np.max(row_gradient_sum[start:end])
            local_mean = np.mean(row_gradient_sum[start:end])

            if row_gradient_sum[y] >= local_max * 0.9 and row_gradient_sum[y] > local_mean * 1.5:
                horizontal_lines.append(y)

        return self._group_and_create_lines(horizontal_lines, w)

    def _algo_lsd(self, image: np.ndarray) -> List[np.ndarray]:
        """Algorithm 3: LSD (Line Segment Detector)."""
        h, w = image.shape[:2]

        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        lsd = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD)
        lines, _, _, _ = lsd.detect(enhanced)

        horizontal_lines = []
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                dx = abs(x2 - x1)
                dy = abs(y2 - y1)

                if dx > w // 20:
                    if dx > 0:
                        angle = np.arctan(dy / dx) * 180 / np.pi
                        if angle < 8:
                            horizontal_lines.append(int((y1 + y2) // 2))

        return self._group_and_create_lines(horizontal_lines, w)

    def _algo_adaptive_morphological(self, image: np.ndarray) -> List[np.ndarray]:
        """Algorithm 4: Adaptive Threshold + Morphological Operations."""
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
    # Grid Overlay Methods
    # =========================================================================

    def create_grid_overlay(
        self,
        image: np.ndarray,
        algorithm: int = 1
    ) -> GridOverlayResult:
        """
        Create an overlay showing detected horizontal grid lines.

        Args:
            image: Input image
            algorithm: Detection algorithm (0=original, 1-4=detection methods)

        Returns:
            GridOverlayResult with overlay image
        """
        algo_names = {
            0: "Original",
            1: "Canny+Hough",
            2: "Vertical Gradient",
            3: "LSD",
            4: "Adaptive+Morphological"
        }

        try:
            if algorithm == 0:
                return GridOverlayResult(
                    overlay_image=image.copy(),
                    vertical_lines=0,
                    horizontal_lines=0,
                    success=True,
                    message="Original image"
                )

            horizontal_lines = self.detect_horizontal_lines(image, algorithm)
            overlay = image.copy()

            for line in horizontal_lines:
                x1, y1, x2, y2 = line
                cv2.line(overlay, (x1, y1), (x2, y2), (0, 255, 0), 2)

            return GridOverlayResult(
                overlay_image=overlay,
                vertical_lines=0,
                horizontal_lines=len(horizontal_lines),
                success=True,
                message=f"[{algo_names.get(algorithm, 'Unknown')}] Detected {len(horizontal_lines)} horizontal lines"
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
