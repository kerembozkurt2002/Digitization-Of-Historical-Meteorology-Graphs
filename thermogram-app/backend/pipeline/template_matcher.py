"""
Template Matcher - Detects "10" labels in thermogram images using template matching.
"""

import cv2
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class MatchResult:
    """Result of template matching operation."""
    success: bool
    message: str
    boxes: List[Tuple[int, int, int, int]]  # List of (x, y, w, h) bounding boxes
    matched_image: np.ndarray | None = None
    calibration_line_y: int | None = None  # Y coordinate of the calibration line


class TemplateMatcher:
    """Detects "10" labels using multi-scale template matching."""

    def __init__(self, template_dir: str = None, threshold: float = 0.65):
        """
        Initialize the template matcher.

        Args:
            template_dir: Directory containing template images (1.png, 2.png, etc.)
            threshold: Matching threshold (0.0 to 1.0), higher = stricter matching
        """
        if template_dir is None:
            # Default to sample10s folder relative to project root
            template_dir = Path(__file__).parent.parent.parent.parent / "sample10s"

        self.template_dir = Path(template_dir)
        self.threshold = threshold
        self.templates: List[np.ndarray] = []
        self.scales = [1.3, 1.4, 1.5]  # Scale up templates to match actual "10" size

        self._load_templates()

    def _load_templates(self):
        """Load all template images from the template directory."""
        if not self.template_dir.exists():
            raise ValueError(f"Template directory not found: {self.template_dir}")

        # Load all PNG files in the directory
        template_files = sorted(self.template_dir.glob("*.png"))

        if not template_files:
            raise ValueError(f"No template images found in: {self.template_dir}")

        for template_file in template_files:
            template = cv2.imread(str(template_file), cv2.IMREAD_GRAYSCALE)
            if template is not None:
                self.templates.append(template)

        if not self.templates:
            raise ValueError("Failed to load any template images")

    def _non_max_suppression(self, boxes: List[Tuple[int, int, int, int]],
                              scores: List[float],
                              overlap_thresh: float = 0.3) -> List[Tuple[int, int, int, int]]:
        """
        Apply non-maximum suppression to remove overlapping boxes.

        Args:
            boxes: List of (x, y, w, h) bounding boxes
            scores: List of matching scores for each box
            overlap_thresh: IoU threshold for suppression

        Returns:
            List of filtered bounding boxes
        """
        if not boxes:
            return []

        # Convert to numpy arrays
        boxes_arr = np.array(boxes)
        scores_arr = np.array(scores)

        # Convert (x, y, w, h) to (x1, y1, x2, y2)
        x1 = boxes_arr[:, 0]
        y1 = boxes_arr[:, 1]
        x2 = boxes_arr[:, 0] + boxes_arr[:, 2]
        y2 = boxes_arr[:, 1] + boxes_arr[:, 3]

        # Calculate areas
        areas = (x2 - x1) * (y2 - y1)

        # Sort by scores (descending)
        order = scores_arr.argsort()[::-1]

        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)

            if order.size == 1:
                break

            # Calculate IoU with remaining boxes
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])

            w = np.maximum(0, xx2 - xx1)
            h = np.maximum(0, yy2 - yy1)

            intersection = w * h
            iou = intersection / (areas[i] + areas[order[1:]] - intersection)

            # Keep boxes with IoU below threshold
            inds = np.where(iou <= overlap_thresh)[0]
            order = order[inds + 1]

        return [(int(boxes[i][0]), int(boxes[i][1]), int(boxes[i][2]), int(boxes[i][3])) for i in keep]

    def match(self, image: np.ndarray) -> MatchResult:
        """
        Find all "10" labels in the image using template matching.

        Args:
            image: Input image (BGR or grayscale)

        Returns:
            MatchResult with detected bounding boxes and annotated image
        """
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Normalize contrast for better matching
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray_norm = clahe.apply(gray)

        # Also create edge version for edge-based matching
        gray_edges = cv2.Canny(gray, 50, 150)

        all_boxes = []
        all_scores = []

        # Try each template at different scales
        for template in self.templates:
            # Apply same normalization to template
            template_norm = clahe.apply(template)
            template_edges = cv2.Canny(template, 50, 150)

            for scale in self.scales:
                # Resize templates
                new_w = int(template_norm.shape[1] * scale)
                new_h = int(template_norm.shape[0] * scale)

                if new_w < 5 or new_h < 5:
                    continue

                scaled_template = cv2.resize(template_norm, (new_w, new_h))
                scaled_template_edges = cv2.resize(template_edges, (new_w, new_h))

                # Skip if template is larger than image
                if scaled_template.shape[0] > gray_norm.shape[0] or scaled_template.shape[1] > gray_norm.shape[1]:
                    continue

                # Method 1: Normal template matching
                result1 = cv2.matchTemplate(gray_norm, scaled_template, cv2.TM_CCOEFF_NORMED)

                # Method 2: Edge-based matching
                result2 = cv2.matchTemplate(gray_edges, scaled_template_edges, cv2.TM_CCOEFF_NORMED)

                # Combine results (take max)
                result = np.maximum(result1, result2)

                # Find locations above threshold
                locations = np.where(result >= self.threshold)

                for pt in zip(*locations[::-1]):  # Switch x and y
                    x, y = int(pt[0]), int(pt[1])
                    w, h = int(scaled_template.shape[1]), int(scaled_template.shape[0])
                    score = float(result[y, x])

                    all_boxes.append((x, y, w, h))
                    all_scores.append(score)

        # Apply non-maximum suppression
        if all_boxes:
            filtered_boxes = self._non_max_suppression(all_boxes, all_scores)
        else:
            filtered_boxes = []

        # Create annotated image
        if len(image.shape) == 2:
            annotated = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            annotated = image.copy()

        # Draw bounding boxes
        for (x, y, w, h) in filtered_boxes:
            cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 0, 255), 2)  # Red boxes

        # Find calibration line from most common y-axis group
        calibration_line_y = None
        if filtered_boxes:
            calibration_line_y = self._find_calibration_line(filtered_boxes, annotated, image)

        return MatchResult(
            success=True,
            message=f"Found {len(filtered_boxes)} matches, calibration line at y={calibration_line_y}",
            boxes=filtered_boxes,
            matched_image=annotated,
            calibration_line_y=calibration_line_y
        )

    def _find_calibration_line(
        self,
        boxes: List[Tuple[int, int, int, int]],
        annotated: np.ndarray,
        original_image: np.ndarray,
        y_tolerance: int = 30
    ) -> int | None:
        """
        Find the calibration line based on most common y-axis group of boxes.

        Args:
            boxes: List of (x, y, w, h) bounding boxes
            annotated: Image to draw on
            original_image: Original image for horizontal line detection
            y_tolerance: Tolerance for grouping boxes by y-axis

        Returns:
            Y coordinate of the calibration line, or None if not found
        """
        if not boxes:
            return None

        # Calculate center y for each box
        center_ys = [(box[1] + box[3] // 2) for box in boxes]

        # Group by y-axis (within tolerance)
        y_groups: dict[int, List[int]] = {}
        for cy in center_ys:
            found_group = False
            for group_y in list(y_groups.keys()):
                if abs(cy - group_y) <= y_tolerance:
                    y_groups[group_y].append(cy)
                    found_group = True
                    break
            if not found_group:
                y_groups[cy] = [cy]

        if not y_groups:
            return None

        # Find the most populated group
        best_group_y = max(y_groups.keys(), key=lambda y: len(y_groups[y]))
        best_group = y_groups[best_group_y]

        # Calculate average y of the best group
        avg_y = int(sum(best_group) / len(best_group))

        # Get horizontal lines from dewarper
        from pipeline.dewarper import Dewarper
        dewarper = Dewarper()
        horizontal_lines = dewarper.detect_horizontal_lines(original_image)

        if not horizontal_lines:
            return None

        # Get y positions of horizontal lines
        line_y_positions = [int(line[1]) for line in horizontal_lines]

        # Find nearest horizontal line
        nearest_line_y = min(line_y_positions, key=lambda y: abs(y - avg_y))

        # Draw the calibration line in black (2px)
        img_w = annotated.shape[1]
        cv2.line(annotated, (0, nearest_line_y), (img_w - 1, nearest_line_y), (0, 0, 0), 2)

        return nearest_line_y
