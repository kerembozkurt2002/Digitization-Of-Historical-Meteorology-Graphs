"""
Segmenter Module - Stage 4 of the thermogram processing pipeline.

Extracts the temperature curve from the grid using color detection and morphology.
"""

import cv2
import numpy as np
import time
from typing import List, Optional, Tuple
from skimage.morphology import skeletonize

from models import (
    SegmentResult,
    CurveSegment,
    TimingInfo,
)
from configs import ChartConfig, SegmentConfig


class Segmenter:
    """
    Segments the temperature curve from the thermogram.

    Stage 4 of the pipeline:
    1. Detect curve color (typically dark ink on grid)
    2. Remove grid lines via inpainting
    3. Extract and skeletonize the curve
    4. Identify connected segments
    """

    def __init__(
        self,
        config: Optional[ChartConfig] = None,
        debug: bool = False
    ):
        """
        Initialize segmenter.

        Args:
            config: Chart configuration (uses defaults if None)
            debug: Enable debug mode
        """
        self.config = config
        self.segment_config = config.segment if config else SegmentConfig()
        self.debug = debug
        self.debug_images = {}

    def segment(
        self,
        image: np.ndarray,
        grid_mask: Optional[np.ndarray] = None
    ) -> SegmentResult:
        """
        Segment the temperature curve from the image.

        Args:
            image: Processed image (from dewarping stage)
            grid_mask: Optional mask of grid lines to remove

        Returns:
            SegmentResult with curve mask and segments
        """
        start_time = time.perf_counter()

        try:
            h, w = image.shape[:2]

            # Step 1: Detect curve color
            curve_color = self._detect_curve_color(image)

            # Step 2: Create curve mask
            curve_mask = self._create_curve_mask(image, curve_color)

            if self.debug:
                self.debug_images['initial_curve_mask'] = curve_mask.copy()

            # Step 3: Remove grid if mask provided
            if grid_mask is not None:
                grid_removed = self._remove_grid(image, grid_mask)
            else:
                grid_removed = image.copy()

            # Step 4: Refine curve mask
            curve_mask = self._refine_mask(curve_mask)

            if self.debug:
                self.debug_images['refined_curve_mask'] = curve_mask.copy()

            # Step 5: Skeletonize
            skeleton = self._skeletonize(curve_mask)

            if self.debug:
                self.debug_images['skeleton'] = skeleton.copy()

            # Step 6: Extract segments
            segments = self._extract_segments(skeleton)

            # Compute curve width
            curve_width = self._compute_curve_width(curve_mask, skeleton)

            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000

            return SegmentResult(
                curve_mask=curve_mask,
                skeleton_image=skeleton,
                grid_removed_image=grid_removed,
                segments=segments,
                curve_color_hsv=curve_color,
                curve_width_avg=curve_width,
                success=True,
                message=f"Segmentation successful. Found {len(segments)} curve segment(s)",
                timing=TimingInfo(
                    stage_name="segment",
                    start_time=start_time,
                    end_time=end_time,
                    duration_ms=duration_ms
                )
            )

        except Exception as e:
            end_time = time.perf_counter()
            h, w = image.shape[:2]
            return SegmentResult(
                curve_mask=np.zeros((h, w), dtype=np.uint8),
                skeleton_image=np.zeros((h, w), dtype=np.uint8),
                grid_removed_image=image,
                success=False,
                message=f"Segmentation failed: {str(e)}",
                timing=TimingInfo(
                    stage_name="segment",
                    start_time=start_time,
                    end_time=end_time,
                    duration_ms=(end_time - start_time) * 1000
                )
            )

    def _detect_curve_color(self, image: np.ndarray) -> Optional[Tuple[int, int, int]]:
        """
        Detect the curve color in HSV space.

        Args:
            image: Input image (BGR)

        Returns:
            HSV color tuple or None
        """
        cfg = self.segment_config

        # Convert to HSV
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # The curve is typically dark (low value) with low saturation
        # Use the configured ranges
        mask = cv2.inRange(
            hsv,
            np.array([cfg.curve_hue_min, cfg.curve_sat_min, cfg.curve_val_min]),
            np.array([cfg.curve_hue_max, cfg.curve_sat_max, cfg.curve_val_max])
        )

        # Find dominant color in masked region
        masked_hsv = hsv[mask > 0]
        if len(masked_hsv) > 0:
            mean_hsv = np.mean(masked_hsv, axis=0)
            return tuple(int(v) for v in mean_hsv)

        return None

    def _create_curve_mask(
        self,
        image: np.ndarray,
        curve_color: Optional[Tuple[int, int, int]]
    ) -> np.ndarray:
        """
        Create binary mask of the curve.

        Args:
            image: Input image (BGR)
            curve_color: Detected curve color in HSV

        Returns:
            Binary mask
        """
        cfg = self.segment_config

        # Convert to grayscale for intensity-based detection
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # The curve is typically darker than the background
        # Use adaptive thresholding to detect dark regions
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2
        )

        return binary

    def _remove_grid(
        self,
        image: np.ndarray,
        grid_mask: np.ndarray
    ) -> np.ndarray:
        """
        Remove grid lines using inpainting.

        Args:
            image: Input image
            grid_mask: Binary mask of grid lines

        Returns:
            Image with grid removed
        """
        # Dilate grid mask slightly
        kernel = np.ones((3, 3), np.uint8)
        dilated_mask = cv2.dilate(grid_mask, kernel, iterations=1)

        # Inpaint
        inpainted = cv2.inpaint(image, dilated_mask, 3, cv2.INPAINT_TELEA)

        return inpainted

    def _refine_mask(self, mask: np.ndarray) -> np.ndarray:
        """
        Refine curve mask using morphological operations.

        Args:
            mask: Initial binary mask

        Returns:
            Refined mask
        """
        cfg = self.segment_config
        kernel_size = cfg.curve_kernel_size

        # Remove small noise
        kernel = np.ones((kernel_size, kernel_size), np.uint8)
        opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # Close small gaps
        closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)

        return closed

    def _skeletonize(self, mask: np.ndarray) -> np.ndarray:
        """
        Create skeleton of the curve.

        Args:
            mask: Binary mask

        Returns:
            Skeletonized image
        """
        # Normalize to 0-1 for skimage
        binary = mask > 127

        # Skeletonize
        skeleton = skeletonize(binary)

        # Convert back to uint8
        return (skeleton * 255).astype(np.uint8)

    def _extract_segments(self, skeleton: np.ndarray) -> List[CurveSegment]:
        """
        Extract connected curve segments from skeleton.

        Args:
            skeleton: Skeletonized curve image

        Returns:
            List of CurveSegment objects
        """
        cfg = self.segment_config

        # Find connected components
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            skeleton, connectivity=8
        )

        segments = []

        for label in range(1, num_labels):  # Skip background (label 0)
            # Get component statistics
            area = stats[label, cv2.CC_STAT_AREA]
            x = stats[label, cv2.CC_STAT_LEFT]
            width = stats[label, cv2.CC_STAT_WIDTH]

            # Filter by minimum length
            if area < cfg.min_curve_length:
                continue

            # Extract points
            component_mask = (labels == label)
            points = np.where(component_mask)
            point_list = list(zip(points[1], points[0]))  # (x, y) format

            # Sort by x coordinate
            point_list.sort(key=lambda p: p[0])

            # Compute confidence based on continuity
            confidence = min(1.0, area / cfg.min_curve_length)

            segments.append(CurveSegment(
                points=point_list,
                start_x=x,
                end_x=x + width,
                confidence=confidence
            ))

        # Sort segments by start_x
        segments.sort(key=lambda s: s.start_x)

        return segments

    def _compute_curve_width(
        self,
        mask: np.ndarray,
        skeleton: np.ndarray
    ) -> float:
        """
        Compute average curve width.

        Args:
            mask: Binary curve mask
            skeleton: Skeletonized curve

        Returns:
            Average width in pixels
        """
        skeleton_area = np.sum(skeleton > 0)
        mask_area = np.sum(mask > 0)

        if skeleton_area == 0:
            return 1.0

        # Average width approximation
        return mask_area / skeleton_area


def segment_image(
    image: np.ndarray,
    config: Optional[ChartConfig] = None,
    grid_mask: Optional[np.ndarray] = None
) -> SegmentResult:
    """
    Convenience function to segment an image.

    Args:
        image: Input image
        config: Chart configuration (optional)
        grid_mask: Grid mask for removal (optional)

    Returns:
        SegmentResult
    """
    segmenter = Segmenter(config=config)
    return segmenter.segment(image, grid_mask=grid_mask)


__all__ = ['Segmenter', 'segment_image']
