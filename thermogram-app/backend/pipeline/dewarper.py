"""
Dewarper Module - Straightens curved grid lines in thermogram images

The thermogram charts have curved/distorted grid lines. This module:
1. Detects the grid lines using edge detection and Hough transform
2. Fits curves to the detected lines
3. Computes a transformation to straighten the grid
4. Applies the transformation to produce a dewarped image
"""

import cv2
import numpy as np
from dataclasses import dataclass
from typing import Tuple, List, Optional
from scipy import ndimage


@dataclass
class DewarpResult:
    """Result of dewarping operation"""
    original_image: np.ndarray
    straightened_image: np.ndarray
    forward_transform: np.ndarray  # Original -> Straightened
    inverse_transform: np.ndarray  # Straightened -> Original
    grid_lines_detected: int
    success: bool
    message: str


@dataclass
class GridOverlayResult:
    """Result of grid overlay operation"""
    overlay_image: np.ndarray
    vertical_lines: int
    horizontal_lines: int
    success: bool
    message: str


@dataclass
class FlattenedGridResult:
    """Result of flattened grid operation"""
    flattened_image: np.ndarray
    vertical_lines: int
    horizontal_lines: int
    success: bool
    message: str


class Dewarper:
    """
    Dewarps thermogram images by detecting and straightening curved grid lines.
    """

    def __init__(self, debug: bool = False):
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
        """
        try:
            h, w = image.shape[:2]

            # Step 1: Create vertical line mask
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

            # Enhance contrast
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)

            # Adaptive threshold - invert so lines are white
            binary = cv2.adaptiveThreshold(
                enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV, 15, 2
            )

            # Strong vertical morphology to isolate vertical structures
            kernel_v = np.ones((25, 1), np.uint8)
            vertical_mask = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_v)

            # Close small gaps
            kernel_close = np.ones((10, 1), np.uint8)
            vertical_mask = cv2.morphologyEx(vertical_mask, cv2.MORPH_CLOSE, kernel_close)

            # Step 2: Trace vertical lines by scanning at different y-levels
            num_samples = 50  # Number of y-levels to sample
            y_samples = np.linspace(h * 0.1, h * 0.9, num_samples).astype(int)

            # For each y-level, find x-positions where vertical lines exist
            line_traces = {}  # {line_id: [(y, x), ...]}

            # Minimum spacing between lines (to avoid detecting same line twice)
            min_line_spacing = 20

            for y in y_samples:
                row = vertical_mask[y, :]

                # Find runs of white pixels (line crossings)
                in_line = False
                line_start = 0

                for x in range(w):
                    if row[x] > 127 and not in_line:
                        in_line = True
                        line_start = x
                    elif row[x] <= 127 and in_line:
                        in_line = False
                        line_center = (line_start + x) // 2

                        # Find which existing line this belongs to, or create new
                        matched = False
                        for line_id in line_traces:
                            # Check if this point is close to existing line
                            last_points = [p for p in line_traces[line_id] if abs(p[0] - y) < h * 0.2]
                            if last_points:
                                last_x = np.mean([p[1] for p in last_points])
                                if abs(line_center - last_x) < min_line_spacing:
                                    line_traces[line_id].append((y, line_center))
                                    matched = True
                                    break

                        if not matched:
                            # Create new line
                            new_id = len(line_traces)
                            line_traces[new_id] = [(y, line_center)]

            # Filter lines that don't have enough points
            valid_lines = {k: v for k, v in line_traces.items() if len(v) >= num_samples * 0.5}

            if len(valid_lines) < 3:
                return DewarpResult(
                    original_image=image,
                    straightened_image=image,
                    forward_transform=np.eye(3),
                    inverse_transform=np.eye(3),
                    grid_lines_detected=len(valid_lines),
                    success=False,
                    message=f"Not enough vertical lines detected: {len(valid_lines)}"
                )

            # Step 3: For each line, fit a curve and compute target x (straight)
            line_curves = []  # [(target_x, curve_func), ...]

            for line_id, points in valid_lines.items():
                points = np.array(points)
                y_vals = points[:, 0]
                x_vals = points[:, 1]

                # Target x is the median x (where the line should be when straight)
                target_x = np.median(x_vals)

                # Fit quadratic: x = a*y^2 + b*y + c
                try:
                    coeffs = np.polyfit(y_vals, x_vals, 2)
                    curve_func = np.poly1d(coeffs)
                    line_curves.append((target_x, curve_func, y_vals.min(), y_vals.max()))
                except:
                    pass

            if len(line_curves) < 3:
                return DewarpResult(
                    original_image=image,
                    straightened_image=image,
                    forward_transform=np.eye(3),
                    inverse_transform=np.eye(3),
                    grid_lines_detected=len(line_curves),
                    success=False,
                    message="Failed to fit curves to lines"
                )

            # Sort by target_x
            line_curves.sort(key=lambda x: x[0])

            # Step 4: Create displacement map
            map_y, map_x = np.mgrid[0:h, 0:w].astype(np.float32)
            displacement_map = np.zeros((h, w), dtype=np.float32)

            # For each line, compute displacement at all y values
            line_x_targets = np.array([lc[0] for lc in line_curves])

            # Pre-compute displacements for each line
            y_all = np.arange(h)
            line_displacements = []

            for target_x, curve_func, y_min, y_max in line_curves:
                # Displacement = actual_x - target_x (how much to shift left to straighten)
                actual_x = curve_func(y_all)
                disp = actual_x - target_x

                # Limit displacement to reasonable range
                max_disp = w * 0.1  # Max 10% of width
                disp = np.clip(disp, -max_disp, max_disp)

                line_displacements.append(disp)

            line_displacements = np.array(line_displacements)

            # Interpolate displacement for all x positions
            for x in range(w):
                # Find surrounding lines
                idx = np.searchsorted(line_x_targets, x)

                if idx == 0:
                    displacement_map[:, x] = line_displacements[0]
                elif idx >= len(line_curves):
                    displacement_map[:, x] = line_displacements[-1]
                else:
                    # Linear interpolation between two nearest lines
                    x_left = line_x_targets[idx - 1]
                    x_right = line_x_targets[idx]
                    t = (x - x_left) / (x_right - x_left) if x_right != x_left else 0.5
                    displacement_map[:, x] = (1 - t) * line_displacements[idx - 1] + t * line_displacements[idx]

            # Smooth displacement map
            displacement_map = cv2.GaussianBlur(displacement_map, (15, 15), 0)

            # Step 5: Apply remapping
            map_x_new = map_x - displacement_map
            map_x_new = np.clip(map_x_new, 0, w - 1)

            straightened = cv2.remap(
                image,
                map_x_new,
                map_y,
                cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_REPLICATE
            )

            return DewarpResult(
                original_image=image,
                straightened_image=straightened,
                forward_transform=np.eye(3),
                inverse_transform=np.eye(3),
                grid_lines_detected=len(line_curves),
                success=True,
                message=f"Dewarping successful - {len(line_curves)} lines straightened"
            )

        except Exception as e:
            return DewarpResult(
                original_image=image,
                straightened_image=image,
                forward_transform=np.eye(3),
                inverse_transform=np.eye(3),
                grid_lines_detected=0,
                success=False,
                message=f"Error during dewarping: {str(e)}"
            )

    def _detect_lines_for_dewarp(self, image: np.ndarray) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        """
        Detect grid lines for dewarping - uses more relaxed angle thresholds
        to get more data points for curve fitting.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        # Apply adaptive thresholding
        adaptive = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2
        )

        h, w = image.shape[:2]

        # Morphological operations to isolate vertical lines
        kernel_v = np.ones((15, 1), np.uint8)
        vertical_mask = cv2.morphologyEx(adaptive, cv2.MORPH_OPEN, kernel_v)
        kernel_v_close = np.ones((5, 1), np.uint8)
        vertical_mask = cv2.morphologyEx(vertical_mask, cv2.MORPH_CLOSE, kernel_v_close)

        # Detect vertical lines - relaxed parameters for dewarping
        lines_v = cv2.HoughLinesP(
            vertical_mask,
            rho=1,
            theta=np.pi / 180,
            threshold=30,
            minLineLength=h // 10,  # Shorter segments OK for dewarp
            maxLineGap=50
        )

        vertical_lines = []

        if lines_v is not None:
            for line in lines_v:
                x1, y1, x2, y2 = line[0]
                dx = abs(x2 - x1)
                dy = abs(y2 - y1)

                # More relaxed angle - within 30 degrees of vertical for dewarping
                if dy > 0:
                    angle_from_vertical = np.arctan(dx / dy) * 180 / np.pi
                else:
                    angle_from_vertical = 90

                if angle_from_vertical <= 30:
                    vertical_lines.append(line[0])

        return vertical_lines, []

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for grid detection."""
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Apply bilateral filter to reduce noise while keeping edges
        filtered = cv2.bilateralFilter(gray, 9, 75, 75)

        # Enhance contrast using CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(filtered)

        if self.debug:
            self.debug_images['preprocessed'] = enhanced

        return enhanced

    def _detect_grid_lines_morphological(self, image: np.ndarray) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        """
        Detect grid lines using morphological operations.
        This works better for thermograms where grid lines are dark on light background.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        # Apply adaptive thresholding to get binary image
        # Grid lines appear as dark lines on lighter paper
        adaptive = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2
        )

        if self.debug:
            self.debug_images['adaptive_threshold'] = adaptive

        # Morphological operations to isolate vertical lines
        # Use a tall thin kernel to preserve vertical structures
        kernel_v = np.ones((15, 1), np.uint8)
        vertical_mask = cv2.morphologyEx(adaptive, cv2.MORPH_OPEN, kernel_v)

        # Connect broken vertical lines
        kernel_v_close = np.ones((5, 1), np.uint8)
        vertical_mask = cv2.morphologyEx(vertical_mask, cv2.MORPH_CLOSE, kernel_v_close)

        # Morphological operations to isolate horizontal lines
        # Use a wide thin kernel to preserve horizontal structures
        kernel_h = np.ones((1, 15), np.uint8)
        horizontal_mask = cv2.morphologyEx(adaptive, cv2.MORPH_OPEN, kernel_h)

        # Connect broken horizontal lines
        kernel_h_close = np.ones((1, 5), np.uint8)
        horizontal_mask = cv2.morphologyEx(horizontal_mask, cv2.MORPH_CLOSE, kernel_h_close)

        if self.debug:
            self.debug_images['vertical_mask'] = vertical_mask
            self.debug_images['horizontal_mask'] = horizontal_mask

        # Detect lines using Hough Transform
        h, w = image.shape[:2]

        # For vertical lines - use shorter minLineLength to catch partial lines
        lines_v = cv2.HoughLinesP(
            vertical_mask,
            rho=1,
            theta=np.pi / 180,
            threshold=30,  # Lower threshold for sensitivity
            minLineLength=h // 8,  # At least 1/8 of image height
            maxLineGap=50  # Allow larger gaps for broken lines
        )

        # For horizontal lines
        lines_h = cv2.HoughLinesP(
            horizontal_mask,
            rho=1,
            theta=np.pi / 180,
            threshold=30,
            minLineLength=w // 16,  # At least 1/16 of image width
            maxLineGap=50
        )

        vertical_lines = []
        horizontal_lines = []

        if lines_v is not None:
            for line in lines_v:
                x1, y1, x2, y2 = line[0]
                # Verify it's more vertical than horizontal (angle > 45 degrees)
                dx = abs(x2 - x1)
                dy = abs(y2 - y1)
                if dy > dx:  # More vertical than horizontal
                    vertical_lines.append(line[0])

        if lines_h is not None:
            for line in lines_h:
                x1, y1, x2, y2 = line[0]
                # Verify it's more horizontal than vertical (angle < 45 degrees)
                dx = abs(x2 - x1)
                dy = abs(y2 - y1)
                if dx > dy:  # More horizontal than vertical
                    horizontal_lines.append(line[0])

        # Cluster and extend lines to full image dimensions
        vertical_lines = self._cluster_and_extend_lines(vertical_lines, 'vertical', image.shape)
        horizontal_lines = self._cluster_and_extend_lines(horizontal_lines, 'horizontal', image.shape)

        return vertical_lines, horizontal_lines

    def detect_horizontal_lines(self, image: np.ndarray, algorithm: int = 1) -> List[np.ndarray]:
        """
        Detect horizontal lines using specified algorithm.
        algorithm: 1=Canny+Hough, 2=Vertical Gradient, 3=LSD, 4=Adaptive+Morphological
        """
        if algorithm == 1:
            return self._algo1_canny_hough(image)
        elif algorithm == 2:
            return self._algo2_vertical_gradient(image)
        elif algorithm == 3:
            return self._algo3_lsd(image)
        elif algorithm == 4:
            return self._algo4_adaptive_morphological(image)
        else:
            return self._algo1_canny_hough(image)

    def _algo1_canny_hough(self, image: np.ndarray) -> List[np.ndarray]:
        """
        Algorithm 1: Canny Edge Detection + Hough Transform
        """
        h, w = image.shape[:2]

        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # CLAHE for better contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)
        # Lower Canny thresholds for more edge detection
        edges = cv2.Canny(blurred, 20, 80, apertureSize=3)

        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=50,  # Lower threshold
            minLineLength=w // 10,  # Shorter minimum length
            maxLineGap=30  # Allow bigger gaps
        )

        horizontal_lines = []
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                dx = abs(x2 - x1)
                dy = abs(y2 - y1)
                if dx > 0:
                    angle = np.arctan(dy / dx) * 180 / np.pi
                    if angle < 8:  # More lenient angle
                        horizontal_lines.append((y1 + y2) // 2)

        return self._group_and_create_lines(horizontal_lines, w)

    def _algo2_vertical_gradient(self, image: np.ndarray) -> List[np.ndarray]:
        """
        Algorithm 2: Vertical Gradient (Derivative-based)
        Looks for strong vertical intensity changes indicating horizontal lines.
        """
        h, w = image.shape[:2]

        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Enhance contrast first
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Calculate vertical gradient (Sobel in Y direction)
        grad_y = cv2.Sobel(enhanced, cv2.CV_64F, 0, 1, ksize=3)
        grad_y = np.abs(grad_y)

        # Sum gradient along each row
        row_gradient_sum = np.sum(grad_y, axis=1)

        # Normalize
        if np.max(row_gradient_sum) > 0:
            row_gradient_sum = row_gradient_sum / np.max(row_gradient_sum)

        # Find peaks using local comparison instead of global threshold
        horizontal_lines = []
        window = 20

        for y in range(h):
            start = max(0, y - window)
            end = min(h, y + window + 1)
            local_max = np.max(row_gradient_sum[start:end])
            local_mean = np.mean(row_gradient_sum[start:end])

            # If this row is a local peak and above local mean
            if row_gradient_sum[y] >= local_max * 0.9 and row_gradient_sum[y] > local_mean * 1.5:
                horizontal_lines.append(y)

        return self._group_and_create_lines(horizontal_lines, w)

    def _algo3_lsd(self, image: np.ndarray) -> List[np.ndarray]:
        """
        Algorithm 3: LSD (Line Segment Detector)
        OpenCV's built-in line segment detector.
        """
        h, w = image.shape[:2]

        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Enhance contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Create LSD detector with more sensitive settings
        # LSD_REFINE_STD = 1 for standard refinement
        lsd = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD)
        lines, _, _, _ = lsd.detect(enhanced)

        horizontal_lines = []
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                dx = abs(x2 - x1)
                dy = abs(y2 - y1)

                # Check if horizontal (angle < 8 degrees) and minimum length
                if dx > w // 20:  # At least 1/20 of image width (more lenient)
                    if dx > 0:
                        angle = np.arctan(dy / dx) * 180 / np.pi
                        if angle < 8:
                            horizontal_lines.append(int((y1 + y2) // 2))

        return self._group_and_create_lines(horizontal_lines, w)

    def _algo4_adaptive_morphological(self, image: np.ndarray) -> List[np.ndarray]:
        """
        Algorithm 4: Adaptive Threshold + Morphological Operations
        Uses adaptive thresholding and horizontal morphological kernel.
        """
        h, w = image.shape[:2]

        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Enhance contrast with stronger CLAHE
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Try multiple block sizes and C values for adaptive thresholding
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
                binary_list.append(binary1)
                binary_list.append(binary2)

        # Try multiple kernel sizes including smaller ones
        horizontal_lines = []
        for kernel_width in [w // 50, w // 40, w // 30, w // 20, w // 15]:
            kernel_h = np.ones((1, max(5, kernel_width)), np.uint8)

            for binary in binary_list:
                horizontal_mask = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_h)
                row_sum = np.sum(horizontal_mask, axis=1)

                if np.max(row_sum) == 0:
                    continue

                # Local peak detection
                window = 12
                for y in range(h):
                    start = max(0, y - window)
                    end = min(h, y + window + 1)
                    local_max = np.max(row_sum[start:end])
                    local_mean = np.mean(row_sum[start:end])

                    if row_sum[y] >= local_max * 0.9 and row_sum[y] > local_mean * 1.2:
                        horizontal_lines.append(y)

        return self._group_and_create_lines(horizontal_lines, w, group_distance=4)

    def _group_and_create_lines(self, y_positions: List[int], width: int, group_distance: int = 10) -> List[np.ndarray]:
        """
        Group nearby y positions and create full-width line arrays.
        """
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

        result = []
        for y in filtered_lines:
            result.append(np.array([0, y, width - 1, y]))

        return result

    def detect_raw_lines(self, image: np.ndarray, strict_horizontal: bool = True) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        """
        Detect grid lines. Currently only returns horizontal lines.
        Vertical line detection is disabled for now.
        """
        # Only detect horizontal lines for now
        horizontal_lines = self.detect_horizontal_lines(image)

        # Vertical lines disabled - return empty list
        vertical_lines = []

        return vertical_lines, horizontal_lines

    def _detect_grid_lines_color(self, image: np.ndarray) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        """
        Detect grid lines using color-based segmentation.
        Fallback method - used if morphological detection fails.
        """
        # Convert to HSV for color detection
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Detect orange/red grid color (typical thermogram grid)
        # Orange hue range: 5-25
        lower_orange = np.array([5, 50, 50])
        upper_orange = np.array([25, 255, 255])
        mask_orange = cv2.inRange(hsv, lower_orange, upper_orange)

        # Also detect red (wraps around 0)
        lower_red1 = np.array([0, 50, 50])
        upper_red1 = np.array([10, 255, 255])
        mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)

        lower_red2 = np.array([170, 50, 50])
        upper_red2 = np.array([180, 255, 255])
        mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)

        # Combine masks
        grid_mask = cv2.bitwise_or(mask_orange, mask_red1)
        grid_mask = cv2.bitwise_or(grid_mask, mask_red2)

        # Clean up mask
        kernel = np.ones((2, 2), np.uint8)
        grid_mask = cv2.morphologyEx(grid_mask, cv2.MORPH_CLOSE, kernel)

        if self.debug:
            self.debug_images['grid_mask'] = grid_mask

        # Detect lines using Hough Transform on the mask
        # Use lower thresholds for better detection
        lines = cv2.HoughLinesP(
            grid_mask,
            rho=1,
            theta=np.pi / 180,
            threshold=30,  # Lower threshold
            minLineLength=20,  # Shorter min length
            maxLineGap=15  # Allow bigger gaps
        )

        if lines is None:
            # Fallback to edge detection
            return self._detect_grid_lines_edges(image)

        vertical_lines = []
        horizontal_lines = []

        for line in lines:
            x1, y1, x2, y2 = line[0]

            # Calculate angle
            dx = x2 - x1
            dy = y2 - y1

            if dx == 0:
                angle = 90
            else:
                angle = np.abs(np.arctan(dy / dx) * 180 / np.pi)

            # More lenient angle classification
            if angle > 60:  # Nearly vertical
                vertical_lines.append(line[0])
            elif angle < 30:  # Nearly horizontal
                horizontal_lines.append(line[0])

        # Cluster and extend lines
        vertical_lines = self._cluster_and_extend_lines(vertical_lines, 'vertical', image.shape)
        horizontal_lines = self._cluster_and_extend_lines(horizontal_lines, 'horizontal', image.shape)

        return vertical_lines, horizontal_lines

    def _detect_grid_lines_edges(self, image: np.ndarray) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        """
        Fallback: Detect grid lines using edge detection.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        # Apply adaptive thresholding
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2
        )

        # Edge detection
        edges = cv2.Canny(gray, 30, 100, apertureSize=3)

        # Combine
        combined = cv2.bitwise_or(binary, edges)

        # Morphological operations to connect broken lines
        kernel_v = np.ones((5, 1), np.uint8)
        kernel_h = np.ones((1, 5), np.uint8)

        # Detect vertical lines
        vertical_mask = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kernel_v)
        vertical_mask = cv2.morphologyEx(vertical_mask, cv2.MORPH_CLOSE, kernel_v)

        # Detect horizontal lines
        horizontal_mask = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kernel_h)
        horizontal_mask = cv2.morphologyEx(horizontal_mask, cv2.MORPH_CLOSE, kernel_h)

        # Hough transform on each mask
        v_lines = cv2.HoughLinesP(vertical_mask, 1, np.pi/180, 30, minLineLength=30, maxLineGap=20)
        h_lines = cv2.HoughLinesP(horizontal_mask, 1, np.pi/180, 30, minLineLength=30, maxLineGap=20)

        vertical_lines = []
        horizontal_lines = []

        if v_lines is not None:
            for line in v_lines:
                vertical_lines.append(line[0])

        if h_lines is not None:
            for line in h_lines:
                horizontal_lines.append(line[0])

        vertical_lines = self._cluster_and_extend_lines(vertical_lines, 'vertical', image.shape)
        horizontal_lines = self._cluster_and_extend_lines(horizontal_lines, 'horizontal', image.shape)

        return vertical_lines, horizontal_lines

    def _detect_grid_lines(self, gray: np.ndarray) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        """
        Detect vertical and horizontal grid lines using edge detection.
        """
        # Edge detection with lower thresholds
        edges = cv2.Canny(gray, 30, 100, apertureSize=3)

        if self.debug:
            self.debug_images['edges'] = edges

        # Detect lines using Hough Transform with lower thresholds
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=50,
            minLineLength=30,
            maxLineGap=15
        )

        if lines is None:
            return [], []

        vertical_lines = []
        horizontal_lines = []

        for line in lines:
            x1, y1, x2, y2 = line[0]

            # Calculate angle
            if x2 - x1 == 0:
                angle = 90
            else:
                angle = np.abs(np.arctan((y2 - y1) / (x2 - x1)) * 180 / np.pi)

            # Classify as vertical or horizontal with more lenient thresholds
            if angle > 60:  # Nearly vertical
                vertical_lines.append(line[0])
            elif angle < 30:  # Nearly horizontal
                horizontal_lines.append(line[0])

        # Cluster and merge similar lines
        vertical_lines = self._cluster_and_extend_lines(vertical_lines, 'vertical', gray.shape)
        horizontal_lines = self._cluster_and_extend_lines(horizontal_lines, 'horizontal', gray.shape)

        return vertical_lines, horizontal_lines

    def _cluster_and_extend_lines(self, lines: List[np.ndarray], axis: str, image_shape: Tuple, threshold: int = 10) -> List[np.ndarray]:
        """
        Cluster nearby lines, merge them, and extend to full image dimension.
        """
        if len(lines) == 0:
            return []

        lines = np.array(lines)
        h, w = image_shape[:2]

        if axis == 'vertical':
            # Sort by x-coordinate (middle of line)
            positions = (lines[:, 0] + lines[:, 2]) / 2
        else:
            # Sort by y-coordinate (middle of line)
            positions = (lines[:, 1] + lines[:, 3]) / 2

        # Sort lines by position
        sorted_indices = np.argsort(positions)
        sorted_lines = lines[sorted_indices]
        sorted_positions = positions[sorted_indices]

        # Cluster nearby lines - compare with previous line position
        clusters = []
        current_cluster = [sorted_lines[0]]

        for i in range(1, len(sorted_lines)):
            # Compare with the previous line (not cluster start)
            if sorted_positions[i] - sorted_positions[i - 1] < threshold:
                current_cluster.append(sorted_lines[i])
            else:
                clusters.append(current_cluster)
                current_cluster = [sorted_lines[i]]

        clusters.append(current_cluster)

        # Get representative line for each cluster and extend it
        result = []
        for cluster in clusters:
            cluster = np.array(cluster)

            if axis == 'vertical':
                # Average x position
                avg_x = int(np.mean((cluster[:, 0] + cluster[:, 2]) / 2))
                # Extend from top to bottom
                result.append(np.array([avg_x, 0, avg_x, h - 1]))
            else:
                # Average y position
                avg_y = int(np.mean((cluster[:, 1] + cluster[:, 3]) / 2))
                # Extend from left to right
                result.append(np.array([0, avg_y, w - 1, avg_y]))

        return result

    def _cluster_lines(self, lines: List[np.ndarray], axis: str, threshold: int = 20) -> List[np.ndarray]:
        """
        Cluster nearby lines and return representative lines.
        """
        if len(lines) == 0:
            return []

        lines = np.array(lines)

        if axis == 'vertical':
            positions = (lines[:, 0] + lines[:, 2]) / 2
        else:
            positions = (lines[:, 1] + lines[:, 3]) / 2

        sorted_indices = np.argsort(positions)
        sorted_lines = lines[sorted_indices]
        sorted_positions = positions[sorted_indices]

        clusters = []
        current_cluster = [sorted_lines[0]]
        current_pos = sorted_positions[0]

        for i in range(1, len(sorted_lines)):
            if sorted_positions[i] - current_pos < threshold:
                current_cluster.append(sorted_lines[i])
            else:
                clusters.append(current_cluster)
                current_cluster = [sorted_lines[i]]
                current_pos = sorted_positions[i]

        clusters.append(current_cluster)

        result = []
        for cluster in clusters:
            cluster = np.array(cluster)
            avg_line = np.mean(cluster, axis=0).astype(int)
            result.append(avg_line)

        return result

    def _find_grid_intersections(
        self,
        vertical_lines: List[np.ndarray],
        horizontal_lines: List[np.ndarray],
        image_shape: Tuple[int, ...]
    ) -> np.ndarray:
        """
        Find intersection points between vertical and horizontal lines.
        """
        intersections = []

        for v_line in vertical_lines:
            vx1, vy1, vx2, vy2 = v_line

            for h_line in horizontal_lines:
                hx1, hy1, hx2, hy2 = h_line

                point = self._line_intersection(
                    (vx1, vy1), (vx2, vy2),
                    (hx1, hy1), (hx2, hy2)
                )

                if point is not None:
                    x, y = point
                    if 0 <= x < image_shape[1] and 0 <= y < image_shape[0]:
                        intersections.append([x, y])

        return np.array(intersections, dtype=np.float32) if intersections else np.array([])

    def _line_intersection(
        self,
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        p3: Tuple[float, float],
        p4: Tuple[float, float]
    ) -> Optional[Tuple[float, float]]:
        """
        Find intersection point of two lines defined by (p1,p2) and (p3,p4).
        """
        x1, y1 = p1
        x2, y2 = p2
        x3, y3 = p3
        x4, y4 = p4

        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)

        if abs(denom) < 1e-10:
            return None

        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom

        x = x1 + t * (x2 - x1)
        y = y1 + t * (y2 - y1)

        return (x, y)

    def _create_straight_grid(
        self,
        src_points: np.ndarray,
        image_shape: Tuple[int, ...]
    ) -> np.ndarray:
        """
        Create destination points for a straight grid based on source points.
        """
        h, w = image_shape[:2]

        min_x, min_y = src_points.min(axis=0)
        max_x, max_y = src_points.max(axis=0)

        sorted_indices = np.lexsort((src_points[:, 0], src_points[:, 1]))
        sorted_points = src_points[sorted_indices]

        y_values = sorted_points[:, 1]
        y_diffs = np.diff(y_values)
        y_threshold = np.median(y_diffs[y_diffs > 5]) * 0.5 if len(y_diffs[y_diffs > 5]) > 0 else 20

        rows = []
        current_row = [sorted_points[0]]

        for i in range(1, len(sorted_points)):
            if sorted_points[i, 1] - current_row[0][1] < y_threshold:
                current_row.append(sorted_points[i])
            else:
                rows.append(current_row)
                current_row = [sorted_points[i]]
        rows.append(current_row)

        for i, row in enumerate(rows):
            rows[i] = sorted(row, key=lambda p: p[0])

        n_rows = len(rows)
        n_cols = max(len(row) for row in rows)

        grid_height = max_y - min_y
        grid_width = max_x - min_x

        dst_points = []
        src_points_ordered = []

        for i, row in enumerate(rows):
            for j, point in enumerate(row):
                dst_x = min_x + (j / max(1, len(row) - 1)) * grid_width
                dst_y = min_y + (i / max(1, n_rows - 1)) * grid_height

                dst_points.append([dst_x, dst_y])
                src_points_ordered.append(point)

        return np.array(dst_points, dtype=np.float32)


    def create_grid_overlay(self, image: np.ndarray, algorithm: int = 1) -> GridOverlayResult:
        """
        Create an overlay showing detected horizontal grid lines on top of the original image.
        algorithm: 0=Original only, 1=Canny+Hough, 2=Vertical Gradient, 3=LSD, 4=Adaptive+Morphological
        """
        algo_names = {
            0: "Original",
            1: "Canny+Hough",
            2: "Vertical Gradient",
            3: "LSD",
            4: "Adaptive+Morphological"
        }
        try:
            # Algorithm 0 = return original without any overlay
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

            # Draw horizontal lines in green (BGR: 0, 255, 0) - thickness 2
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
        Create an image showing only the detected horizontal grid lines on a white background.
        Vertical detection is disabled for now.
        """
        try:
            h, w = image.shape[:2]

            # Detect horizontal lines
            horizontal_lines = self.detect_horizontal_lines(image)

            # Create white background
            flattened = np.ones((h, w, 3), dtype=np.uint8) * 255

            # Draw horizontal lines in green (full width) - thin line
            for line in horizontal_lines:
                y = line[1]  # y1 = y2 for horizontal lines
                cv2.line(flattened, (0, y), (w-1, y), (0, 255, 0), 1)

            return FlattenedGridResult(
                flattened_image=flattened,
                vertical_lines=0,  # Disabled for now
                horizontal_lines=len(horizontal_lines),
                success=True,
                message=f"Flattened grid with {len(horizontal_lines)} horizontal lines"
            )
        except Exception as e:
            return FlattenedGridResult(
                flattened_image=np.ones((image.shape[0], image.shape[1], 3), dtype=np.uint8) * 255,
                vertical_lines=0,
                horizontal_lines=0,
                success=False,
                message=f"Error creating flattened grid: {str(e)}"
            )

    def create_straightened_image(self, image: np.ndarray) -> FlattenedGridResult:
        """
        Returns the dewarped/straightened image only (no colored overlay lines).
        This shows the final result with the grid naturally straightened.
        """
        try:
            # Dewarp the image
            dewarp_result = self.dewarp(image)

            if not dewarp_result.success:
                return FlattenedGridResult(
                    flattened_image=image,  # Return original if failed
                    vertical_lines=0,
                    horizontal_lines=0,
                    success=False,
                    message=f"Dewarping failed: {dewarp_result.message}"
                )

            # Return the straightened image directly - no colored lines
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


def dewarp_image(image_path: str, output_path: str = None) -> DewarpResult:
    """
    Convenience function to dewarp an image file.
    """
    from utils.image_utils import load_image, save_image

    image = load_image(image_path)

    dewarper = Dewarper(debug=False)
    result = dewarper.dewarp(image)

    if output_path and result.success:
        save_image(result.straightened_image, output_path)

    return result
