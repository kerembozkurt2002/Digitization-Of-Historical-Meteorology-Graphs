"""
Grid detection utility functions.

Shared functions for detecting and processing grid lines in thermogram images.
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional


def cluster_lines(
    lines: List[np.ndarray],
    axis: str,
    threshold: int = 10
) -> List[np.ndarray]:
    """
    Cluster nearby lines and return representative lines.

    Args:
        lines: List of line segments as [x1, y1, x2, y2] arrays
        axis: 'vertical' or 'horizontal'
        threshold: Maximum distance between lines in same cluster

    Returns:
        List of representative lines, one per cluster
    """
    if len(lines) == 0:
        return []

    lines = np.array(lines)

    if axis == 'vertical':
        # Use x-coordinate (middle of line)
        positions = (lines[:, 0] + lines[:, 2]) / 2
    else:
        # Use y-coordinate (middle of line)
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


def extend_lines_to_bounds(
    lines: List[np.ndarray],
    axis: str,
    image_shape: Tuple[int, int],
    threshold: int = 10
) -> List[np.ndarray]:
    """
    Cluster nearby lines, merge them, and extend to full image dimension.

    Args:
        lines: List of line segments as [x1, y1, x2, y2] arrays
        axis: 'vertical' or 'horizontal'
        image_shape: (height, width) of image
        threshold: Distance threshold for clustering

    Returns:
        List of extended lines spanning full image dimension
    """
    if len(lines) == 0:
        return []

    lines = np.array(lines)
    h, w = image_shape[:2]

    if axis == 'vertical':
        positions = (lines[:, 0] + lines[:, 2]) / 2
    else:
        positions = (lines[:, 1] + lines[:, 3]) / 2

    sorted_indices = np.argsort(positions)
    sorted_lines = lines[sorted_indices]
    sorted_positions = positions[sorted_indices]

    # Cluster nearby lines
    clusters = []
    current_cluster = [sorted_lines[0]]

    for i in range(1, len(sorted_lines)):
        if sorted_positions[i] - sorted_positions[i - 1] < threshold:
            current_cluster.append(sorted_lines[i])
        else:
            clusters.append(current_cluster)
            current_cluster = [sorted_lines[i]]

    clusters.append(current_cluster)

    # Get representative line for each cluster and extend
    result = []
    for cluster in clusters:
        cluster = np.array(cluster)

        if axis == 'vertical':
            avg_x = int(np.mean((cluster[:, 0] + cluster[:, 2]) / 2))
            result.append(np.array([avg_x, 0, avg_x, h - 1]))
        else:
            avg_y = int(np.mean((cluster[:, 1] + cluster[:, 3]) / 2))
            result.append(np.array([0, avg_y, w - 1, avg_y]))

    return result


def line_intersection(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    p3: Tuple[float, float],
    p4: Tuple[float, float]
) -> Optional[Tuple[float, float]]:
    """
    Find intersection point of two lines defined by (p1, p2) and (p3, p4).

    Args:
        p1, p2: Two points defining the first line
        p3, p4: Two points defining the second line

    Returns:
        Intersection point (x, y) or None if lines are parallel
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


def find_grid_intersections(
    vertical_lines: List[np.ndarray],
    horizontal_lines: List[np.ndarray],
    image_shape: Tuple[int, int]
) -> np.ndarray:
    """
    Find intersection points between vertical and horizontal lines.

    Args:
        vertical_lines: List of vertical line segments
        horizontal_lines: List of horizontal line segments
        image_shape: (height, width) of image

    Returns:
        Array of intersection points [[x, y], ...]
    """
    h, w = image_shape[:2]
    intersections = []

    for v_line in vertical_lines:
        vx1, vy1, vx2, vy2 = v_line

        for h_line in horizontal_lines:
            hx1, hy1, hx2, hy2 = h_line

            point = line_intersection(
                (vx1, vy1), (vx2, vy2),
                (hx1, hy1), (hx2, hy2)
            )

            if point is not None:
                x, y = point
                if 0 <= x < w and 0 <= y < h:
                    intersections.append([x, y])

    return np.array(intersections, dtype=np.float32) if intersections else np.array([])


def detect_lines_morphological(
    image: np.ndarray,
    axis: str,
    kernel_length: int = 25,
    kernel_width: int = 1,
    hough_threshold: int = 30,
    min_line_length_ratio: float = 0.125,
    max_gap: int = 50,
    angle_threshold: float = 45.0
) -> List[np.ndarray]:
    """
    Detect lines using morphological operations and Hough transform.

    Args:
        image: Input image (BGR or grayscale)
        axis: 'vertical' or 'horizontal'
        kernel_length: Length of morphological kernel
        kernel_width: Width of morphological kernel
        hough_threshold: Hough transform threshold
        min_line_length_ratio: Minimum line length as ratio of image dimension
        max_gap: Maximum gap for line segment detection
        angle_threshold: Maximum angle deviation from axis (degrees)

    Returns:
        List of detected line segments
    """
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    h, w = gray.shape[:2]

    # Apply adaptive thresholding
    adaptive = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 11, 2
    )

    # Create morphological kernel based on axis
    if axis == 'vertical':
        kernel = np.ones((kernel_length, kernel_width), np.uint8)
        min_line_length = int(h * min_line_length_ratio)
    else:
        kernel = np.ones((kernel_width, kernel_length), np.uint8)
        min_line_length = int(w * min_line_length_ratio)

    # Apply morphological operations
    mask = cv2.morphologyEx(adaptive, cv2.MORPH_OPEN, kernel)

    # Close small gaps
    close_kernel = kernel.copy()
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel)

    # Detect lines using Hough transform
    lines = cv2.HoughLinesP(
        mask,
        rho=1,
        theta=np.pi / 180,
        threshold=hough_threshold,
        minLineLength=min_line_length,
        maxLineGap=max_gap
    )

    detected_lines = []

    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            dx = abs(x2 - x1)
            dy = abs(y2 - y1)

            if axis == 'vertical':
                # Check if more vertical than threshold
                if dy > 0:
                    angle = np.arctan(dx / dy) * 180 / np.pi
                    if angle < angle_threshold:
                        detected_lines.append(line[0])
            else:
                # Check if more horizontal than threshold
                if dx > 0:
                    angle = np.arctan(dy / dx) * 180 / np.pi
                    if angle < angle_threshold:
                        detected_lines.append(line[0])

    return detected_lines


def trace_vertical_lines(
    vertical_mask: np.ndarray,
    num_samples: int = 50,
    min_line_spacing: int = 20,
    min_points_ratio: float = 0.5
) -> dict:
    """
    Trace vertical lines by scanning at different y-levels.

    Args:
        vertical_mask: Binary mask of vertical structures
        num_samples: Number of y-levels to sample
        min_line_spacing: Minimum spacing between lines
        min_points_ratio: Minimum ratio of points required for valid line

    Returns:
        Dictionary mapping line_id to list of (y, x) points
    """
    h, w = vertical_mask.shape[:2]
    y_samples = np.linspace(h * 0.1, h * 0.9, num_samples).astype(int)

    line_traces = {}

    for y in y_samples:
        row = vertical_mask[y, :]

        # Find runs of white pixels
        in_line = False
        line_start = 0

        for x in range(w):
            if row[x] > 127 and not in_line:
                in_line = True
                line_start = x
            elif row[x] <= 127 and in_line:
                in_line = False
                line_center = (line_start + x) // 2

                # Find which existing line this belongs to
                matched = False
                for line_id in line_traces:
                    last_points = [p for p in line_traces[line_id] if abs(p[0] - y) < h * 0.2]
                    if last_points:
                        last_x = np.mean([p[1] for p in last_points])
                        if abs(line_center - last_x) < min_line_spacing:
                            line_traces[line_id].append((y, line_center))
                            matched = True
                            break

                if not matched:
                    new_id = len(line_traces)
                    line_traces[new_id] = [(y, line_center)]

    # Filter lines that don't have enough points
    min_points = int(num_samples * min_points_ratio)
    valid_lines = {k: v for k, v in line_traces.items() if len(v) >= min_points}

    return valid_lines


def fit_line_curves(
    line_traces: dict,
    polynomial_degree: int = 2
) -> List[Tuple[float, np.poly1d, float, float]]:
    """
    Fit polynomial curves to traced lines.

    Args:
        line_traces: Dictionary from trace_vertical_lines
        polynomial_degree: Degree of polynomial to fit

    Returns:
        List of (target_x, curve_function, y_min, y_max) tuples
    """
    line_curves = []

    for _, points in line_traces.items():
        points = np.array(points)
        y_vals = points[:, 0]
        x_vals = points[:, 1]

        # Target x is the median x
        target_x = np.median(x_vals)

        try:
            coeffs = np.polyfit(y_vals, x_vals, polynomial_degree)
            curve_func = np.poly1d(coeffs)
            line_curves.append((target_x, curve_func, y_vals.min(), y_vals.max()))
        except Exception:
            pass

    # Sort by target_x
    line_curves.sort(key=lambda x: x[0])

    return line_curves


def create_displacement_map(
    image_shape: Tuple[int, int],
    line_curves: List[Tuple[float, np.poly1d, float, float]],
    max_displacement_ratio: float = 0.1,
    gaussian_kernel_size: int = 15
) -> np.ndarray:
    """
    Create displacement map for dewarping based on line curves.

    Args:
        image_shape: (height, width) of image
        line_curves: Output from fit_line_curves
        max_displacement_ratio: Maximum displacement as ratio of width
        gaussian_kernel_size: Kernel size for smoothing

    Returns:
        Displacement map array
    """
    h, w = image_shape[:2]

    displacement_map = np.zeros((h, w), dtype=np.float32)
    line_x_targets = np.array([lc[0] for lc in line_curves])

    # Pre-compute displacements for each line
    y_all = np.arange(h)
    line_displacements = []

    for target_x, curve_func, _y_min, _y_max in line_curves:
        actual_x = curve_func(y_all)
        disp = actual_x - target_x

        # Limit displacement
        max_disp = w * max_displacement_ratio
        disp = np.clip(disp, -max_disp, max_disp)

        line_displacements.append(disp)

    line_displacements = np.array(line_displacements)

    # Interpolate displacement for all x positions
    for x in range(w):
        idx = np.searchsorted(line_x_targets, x)

        if idx == 0:
            displacement_map[:, x] = line_displacements[0]
        elif idx >= len(line_curves):
            displacement_map[:, x] = line_displacements[-1]
        else:
            # Linear interpolation
            x_left = line_x_targets[idx - 1]
            x_right = line_x_targets[idx]
            t = (x - x_left) / (x_right - x_left) if x_right != x_left else 0.5
            displacement_map[:, x] = (1 - t) * line_displacements[idx - 1] + t * line_displacements[idx]

    # Smooth displacement map
    if gaussian_kernel_size > 0:
        displacement_map = cv2.GaussianBlur(
            displacement_map,
            (gaussian_kernel_size, gaussian_kernel_size),
            0
        )

    return displacement_map


def apply_displacement_map(
    image: np.ndarray,
    displacement_map: np.ndarray
) -> np.ndarray:
    """
    Apply displacement map to straighten image.

    Args:
        image: Input image
        displacement_map: Horizontal displacement map

    Returns:
        Straightened image
    """
    h, w = image.shape[:2]

    map_y, map_x = np.mgrid[0:h, 0:w].astype(np.float32)
    map_x_new = map_x - displacement_map
    map_x_new = np.clip(map_x_new, 0, w - 1)

    straightened = cv2.remap(
        image,
        map_x_new,
        map_y,
        cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE
    )

    return straightened


__all__ = [
    'cluster_lines',
    'extend_lines_to_bounds',
    'line_intersection',
    'find_grid_intersections',
    'detect_lines_morphological',
    'trace_vertical_lines',
    'fit_line_curves',
    'create_displacement_map',
    'apply_displacement_map',
]
