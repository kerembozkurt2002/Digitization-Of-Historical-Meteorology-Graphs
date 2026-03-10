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
            cfg = self.segment_config
            h, w = image.shape[:2]

            # Choose segmentation method based on config
            if cfg.method == "br_subtract":
                return self._segment_br_subtract(image, start_time)

            # Default: HSV method (original implementation)
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

    def _segment_br_subtract(
        self,
        image: np.ndarray,
        start_time: float
    ) -> SegmentResult:
        """
        Segment curve using B-R channel subtraction method.

        This method removes orange/red grid lines by subtracting the red channel
        from the blue channel, preserving dark/blue ink curves.

        Args:
            image: Input BGR image
            start_time: Start time for timing

        Returns:
            SegmentResult with extracted curve
        """
        cfg = self.segment_config
        h, w = image.shape[:2]

        # Step 1: B-R Channel Subtraction
        # Orange grid lines have high R, low B → B-R is negative (clipped to 0)
        # Dark ink has similar B and R (both low) → B-R ≈ 0 but we catch via dark mask
        b, g, r = cv2.split(image)
        br_diff = cv2.subtract(b, r)

        # Threshold the B-R difference to get potential curve pixels
        _, br_mask = cv2.threshold(br_diff, cfg.br_subtract_threshold, 255, cv2.THRESH_BINARY)

        if self.debug:
            self.debug_images['br_diff'] = br_diff.copy()
            self.debug_images['br_mask'] = br_mask.copy()

        # Step 2: Dark Pixel Mask (catches black/dark blue ink)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        dark_mask = cv2.inRange(
            hsv,
            np.array([0, 0, 0]),
            np.array([180, cfg.dark_pixel_sat_max, cfg.dark_pixel_val_max])
        )

        if self.debug:
            self.debug_images['dark_mask'] = dark_mask.copy()

        # Step 3: Combine masks
        combined_mask = cv2.bitwise_or(br_mask, dark_mask)

        if self.debug:
            self.debug_images['combined_mask'] = combined_mask.copy()

        # Step 4: Morphological Opening to remove noise
        kernel = np.ones((cfg.morph_kernel_size, cfg.morph_kernel_size), np.uint8)
        cleaned_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel)

        if self.debug:
            self.debug_images['cleaned_mask'] = cleaned_mask.copy()

        # Step 5: Column-wise scanning to extract curve points
        curve_points, y_values = self._columnwise_scan(cleaned_mask)

        if not curve_points:
            end_time = time.perf_counter()
            return SegmentResult(
                curve_mask=cleaned_mask,
                skeleton_image=np.zeros((h, w), dtype=np.uint8),
                grid_removed_image=image,
                segments=[],
                success=False,
                message="No curve points found with B-R subtraction method",
                timing=TimingInfo(
                    stage_name="segment",
                    start_time=start_time,
                    end_time=end_time,
                    duration_ms=(end_time - start_time) * 1000
                )
            )

        # Step 6: Create skeleton from extracted points
        skeleton = self._create_skeleton_from_points(curve_points, h, w)

        if self.debug:
            self.debug_images['skeleton'] = skeleton.copy()

        # Step 7: Create segments from points
        segments = self._create_segments_from_points(curve_points, y_values)

        # Compute average curve width from the original cleaned mask
        curve_width = self._compute_curve_width(cleaned_mask, skeleton)

        end_time = time.perf_counter()
        duration_ms = (end_time - start_time) * 1000

        return SegmentResult(
            curve_mask=cleaned_mask,
            skeleton_image=skeleton,
            grid_removed_image=image,
            segments=segments,
            curve_color_hsv=None,
            curve_width_avg=curve_width,
            success=True,
            message=f"B-R segmentation successful. Found {len(curve_points)} curve points",
            timing=TimingInfo(
                stage_name="segment",
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms
            )
        )

    def _columnwise_scan(
        self,
        mask: np.ndarray
    ) -> Tuple[List[Tuple[int, int]], np.ndarray]:
        """
        Scan mask column by column to extract curve points.

        For each column, finds contiguous groups of white pixels and
        selects the one that fits the expected curve thickness.

        Args:
            mask: Binary mask

        Returns:
            Tuple of (list of (x, y) points, array of y values with NaN for gaps)
        """
        cfg = self.segment_config
        h, w = mask.shape

        curve_points = []
        y_values = np.full(w, np.nan)

        for x in range(w):
            column = mask[:, x]
            white_indices = np.where(column > 0)[0]

            if len(white_indices) == 0:
                continue

            # Find contiguous segments in this column
            segments = self._find_contiguous_segments(white_indices)

            # Filter segments by expected curve thickness
            valid_segments = []
            for seg_start, seg_end in segments:
                thickness = seg_end - seg_start + 1
                if cfg.curve_thickness_min <= thickness <= cfg.curve_thickness_max:
                    valid_segments.append((seg_start, seg_end))

            if not valid_segments:
                # If no valid segments, try using the thinnest one
                if segments:
                    thicknesses = [(s[1] - s[0] + 1, s) for s in segments]
                    thicknesses.sort(key=lambda x: x[0])
                    # Take the thinnest segment if it's close to valid range
                    if thicknesses[0][0] <= cfg.curve_thickness_max * 2:
                        valid_segments = [thicknesses[0][1]]

            if valid_segments:
                # Use the median y of the first valid segment
                # (assuming single curve, take the segment closest to typical curve position)
                seg_start, seg_end = valid_segments[0]
                median_y = (seg_start + seg_end) // 2
                curve_points.append((x, median_y))
                y_values[x] = median_y

        return curve_points, y_values

    def _find_contiguous_segments(
        self,
        indices: np.ndarray
    ) -> List[Tuple[int, int]]:
        """
        Find contiguous segments in a sorted array of indices.

        Args:
            indices: Sorted array of y-indices

        Returns:
            List of (start, end) tuples for each contiguous segment
        """
        if len(indices) == 0:
            return []

        segments = []
        seg_start = indices[0]
        seg_end = indices[0]

        for i in range(1, len(indices)):
            if indices[i] == seg_end + 1:
                # Contiguous
                seg_end = indices[i]
            else:
                # Gap found, save current segment
                segments.append((seg_start, seg_end))
                seg_start = indices[i]
                seg_end = indices[i]

        # Save last segment
        segments.append((seg_start, seg_end))

        return segments

    def _create_skeleton_from_points(
        self,
        points: List[Tuple[int, int]],
        height: int,
        width: int
    ) -> np.ndarray:
        """
        Create a skeleton image from extracted curve points.

        Args:
            points: List of (x, y) points
            height: Image height
            width: Image width

        Returns:
            Skeleton image (uint8)
        """
        skeleton = np.zeros((height, width), dtype=np.uint8)

        for x, y in points:
            if 0 <= x < width and 0 <= y < height:
                skeleton[y, x] = 255

        return skeleton

    def _create_segments_from_points(
        self,
        points: List[Tuple[int, int]],
        y_values: np.ndarray
    ) -> List[CurveSegment]:
        """
        Create CurveSegment objects from extracted points.

        Identifies gaps and creates separate segments for continuous runs.

        Args:
            points: List of (x, y) points
            y_values: Array of y values (with NaN for gaps)

        Returns:
            List of CurveSegment objects
        """
        cfg = self.segment_config

        if not points:
            return []

        # Sort points by x
        sorted_points = sorted(points, key=lambda p: p[0])

        # Find continuous segments (where x values are mostly consecutive)
        segments = []
        current_segment_points = [sorted_points[0]]
        max_gap = 10  # Max gap in x before starting new segment

        for i in range(1, len(sorted_points)):
            x_prev = sorted_points[i - 1][0]
            x_curr = sorted_points[i][0]

            if x_curr - x_prev <= max_gap:
                current_segment_points.append(sorted_points[i])
            else:
                # Start new segment
                if len(current_segment_points) >= cfg.min_curve_length:
                    segments.append(self._create_single_segment(current_segment_points))
                current_segment_points = [sorted_points[i]]

        # Don't forget the last segment
        if len(current_segment_points) >= cfg.min_curve_length:
            segments.append(self._create_single_segment(current_segment_points))

        # If no segments meet min length, create one from all points anyway
        if not segments and sorted_points:
            segments.append(self._create_single_segment(sorted_points))

        return segments

    def _create_single_segment(
        self,
        points: List[Tuple[int, int]]
    ) -> CurveSegment:
        """
        Create a single CurveSegment from a list of points.

        Args:
            points: List of (x, y) points

        Returns:
            CurveSegment object
        """
        x_values = [p[0] for p in points]
        confidence = min(1.0, len(points) / self.segment_config.min_curve_length)

        return CurveSegment(
            points=points,
            start_x=min(x_values),
            end_x=max(x_values),
            confidence=confidence
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
