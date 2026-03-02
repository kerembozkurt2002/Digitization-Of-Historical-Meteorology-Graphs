"""
Preprocessor Module - Stage 1 of the thermogram processing pipeline.

Handles image normalization, denoising, contrast enhancement, and ROI detection.
"""

import cv2
import numpy as np
import time
from typing import Optional, Tuple

from models import PreprocessResult, TimingInfo
from configs import ChartConfig, PreprocessConfig


class Preprocessor:
    """
    Preprocesses thermogram images for downstream processing.

    Stage 1 of the pipeline:
    1. Normalize - Color space, bit depth normalization
    2. Denoise - Bilateral filter to reduce noise while preserving edges
    3. Enhance Contrast - CLAHE in LAB color space
    4. Detect ROI - Find chart boundaries (optional crop)
    """

    def __init__(self, config: Optional[ChartConfig] = None, debug: bool = False):
        """
        Initialize preprocessor.

        Args:
            config: Chart configuration (uses defaults if None)
            debug: Enable debug mode for intermediate images
        """
        self.config = config
        self.preprocess_config = config.preprocess if config else PreprocessConfig()
        self.debug = debug
        self.debug_images = {}

    def process(self, image: np.ndarray) -> PreprocessResult:
        """
        Run full preprocessing pipeline.

        Args:
            image: Input image (BGR format)

        Returns:
            PreprocessResult with processed images and metadata
        """
        start_time = time.perf_counter()

        try:
            # Store original
            original = image.copy()

            # Step 1: Normalize
            normalized = self._normalize(image)

            # Step 2: Deskew (rotation correction)
            deskewed, rotation_angle = self._deskew(normalized)

            # Step 3: Denoise
            denoised = self._denoise(deskewed)

            # Step 4: Enhance contrast
            enhanced = self._enhance_contrast(denoised)

            # Step 5: Detect ROI (optional)
            roi_bounds = self._detect_roi(enhanced)

            # Create grayscale version
            if len(enhanced.shape) == 3:
                grayscale = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
            else:
                grayscale = enhanced.copy()

            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000

            return PreprocessResult(
                original_image=original,
                processed_image=enhanced,
                grayscale_image=grayscale,
                roi_bounds=roi_bounds,
                cropped=False,
                normalization_applied=True,
                denoising_applied=True,
                contrast_enhancement_applied=True,
                success=True,
                message="Preprocessing completed successfully",
                timing=TimingInfo(
                    stage_name="preprocess",
                    start_time=start_time,
                    end_time=end_time,
                    duration_ms=duration_ms
                )
            )

        except Exception as e:
            end_time = time.perf_counter()
            return PreprocessResult(
                original_image=image,
                processed_image=image,
                grayscale_image=cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image,
                success=False,
                message=f"Preprocessing failed: {str(e)}",
                timing=TimingInfo(
                    stage_name="preprocess",
                    start_time=start_time,
                    end_time=end_time,
                    duration_ms=(end_time - start_time) * 1000
                )
            )

    def _normalize(self, image: np.ndarray) -> np.ndarray:
        """
        Normalize image color space and bit depth.

        Args:
            image: Input image

        Returns:
            Normalized image in BGR format, 8-bit depth
        """
        # Ensure BGR format
        if len(image.shape) == 2:
            # Grayscale to BGR
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        elif image.shape[2] == 4:
            # BGRA to BGR
            image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

        # Ensure 8-bit depth
        if image.dtype == np.uint16:
            image = (image / 256).astype(np.uint8)
        elif image.dtype == np.float32 or image.dtype == np.float64:
            image = (image * 255).astype(np.uint8)

        if self.debug:
            self.debug_images['normalized'] = image.copy()

        return image

    def _deskew(self, image: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Correct image rotation by analyzing content edges row-by-row.

        Thermograms may be slightly rotated due to manual scanning.
        This detects rotation by finding where dark content starts/ends
        on each row and fitting a line to those edges.

        Args:
            image: Input image (BGR)

        Returns:
            Tuple of (deskewed image, rotation angle in degrees)
        """
        h, w = image.shape[:2]

        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Sample rows across the image height
        num_samples = 20
        sample_rows = np.linspace(h * 0.1, h * 0.9, num_samples).astype(int)

        left_edges = []
        right_edges = []
        dark_threshold = 240  # Pixels darker than this are "content"

        for row in sample_rows:
            row_data = gray[row, :]

            # Find first dark pixel from left (skip first 5% to avoid border artifacts)
            start_x = int(w * 0.05)
            end_x = int(w * 0.95)

            # Left edge: first dark pixel
            left_portion = row_data[start_x:w//2]
            dark_indices = np.where(left_portion < dark_threshold)[0]
            if len(dark_indices) > 0:
                left_x = start_x + dark_indices[0]
                left_edges.append((row, left_x))

            # Right edge: last dark pixel
            right_portion = row_data[w//2:end_x]
            dark_indices = np.where(right_portion < dark_threshold)[0]
            if len(dark_indices) > 0:
                right_x = w//2 + dark_indices[-1]
                right_edges.append((row, right_x))

        # Need at least 5 points to fit reliably
        if len(left_edges) < 5 or len(right_edges) < 5:
            if self.debug:
                self.debug_images['deskewed'] = image.copy()
            return image, 0.0

        # Fit lines to edges and calculate rotation angle
        # Slope is dx/dy, we want angle from horizontal
        left_y = np.array([e[0] for e in left_edges])
        left_x = np.array([e[1] for e in left_edges])
        left_slope, _ = np.polyfit(left_y, left_x, 1)
        left_angle = np.degrees(np.arctan(left_slope))

        right_y = np.array([e[0] for e in right_edges])
        right_x = np.array([e[1] for e in right_edges])
        right_slope, _ = np.polyfit(right_y, right_x, 1)
        right_angle = np.degrees(np.arctan(right_slope))

        # Average the two edge angles
        rotation_angle = (left_angle + right_angle) / 2

        # Only correct if angle is significant but not too extreme
        if abs(rotation_angle) < 0.02:  # Less than 0.02 degree - negligible
            if self.debug:
                self.debug_images['deskewed'] = image.copy()
            return image, 0.0

        if abs(rotation_angle) > 10:  # More than 10 degrees - probably wrong detection
            if self.debug:
                self.debug_images['deskewed'] = image.copy()
            return image, 0.0

        # Rotate image to correct the skew
        center = (w // 2, h // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, rotation_angle, 1.0)

        # Calculate new image size to avoid cropping
        cos = np.abs(rotation_matrix[0, 0])
        sin = np.abs(rotation_matrix[0, 1])
        new_w = int(h * sin + w * cos)
        new_h = int(h * cos + w * sin)

        # Adjust rotation matrix for new size
        rotation_matrix[0, 2] += (new_w - w) / 2
        rotation_matrix[1, 2] += (new_h - h) / 2

        # Apply rotation with white background
        deskewed = cv2.warpAffine(
            image,
            rotation_matrix,
            (new_w, new_h),
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255)
        )

        if self.debug:
            self.debug_images['deskewed'] = deskewed.copy()
            self.debug_images['rotation_angle'] = rotation_angle

        return deskewed, rotation_angle

    def _denoise(self, image: np.ndarray) -> np.ndarray:
        """
        Apply bilateral filter to reduce noise while preserving edges.

        Args:
            image: Input image (BGR)

        Returns:
            Denoised image
        """
        cfg = self.preprocess_config

        denoised = cv2.bilateralFilter(
            image,
            d=cfg.bilateral_d,
            sigmaColor=cfg.bilateral_sigma_color,
            sigmaSpace=cfg.bilateral_sigma_space
        )

        if self.debug:
            self.debug_images['denoised'] = denoised.copy()

        return denoised

    def _enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """
        Enhance contrast using CLAHE in LAB color space.

        Args:
            image: Input image (BGR)

        Returns:
            Contrast-enhanced image
        """
        cfg = self.preprocess_config

        # Convert to LAB color space
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)

        # Split channels
        l, a, b = cv2.split(lab)

        # Apply CLAHE to L channel
        clahe = cv2.createCLAHE(
            clipLimit=cfg.clahe_clip_limit,
            tileGridSize=(cfg.clahe_tile_size, cfg.clahe_tile_size)
        )
        l_enhanced = clahe.apply(l)

        # Merge channels
        lab_enhanced = cv2.merge([l_enhanced, a, b])

        # Convert back to BGR
        enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)

        if self.debug:
            self.debug_images['enhanced'] = enhanced.copy()

        return enhanced

    def _detect_roi(self, image: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """
        Detect the region of interest (chart boundaries).

        Args:
            image: Input image

        Returns:
            ROI bounds (x, y, width, height) or None if detection fails
        """
        h, w = image.shape[:2]
        cfg = self.preprocess_config

        try:
            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()

            # Apply edge detection
            edges = cv2.Canny(gray, 50, 150)

            # Dilate to connect nearby edges
            kernel = np.ones((5, 5), np.uint8)
            dilated = cv2.dilate(edges, kernel, iterations=2)

            # Find contours
            contours, _ = cv2.findContours(
                dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            if not contours:
                return None

            # Find largest contour (likely the chart)
            largest = max(contours, key=cv2.contourArea)
            x, y, cw, ch = cv2.boundingRect(largest)

            # Apply margin
            margin = int(min(h, w) * cfg.roi_margin)
            x = max(0, x - margin)
            y = max(0, y - margin)
            cw = min(w - x, cw + 2 * margin)
            ch = min(h - y, ch + 2 * margin)

            # Validate ROI size (should be at least 50% of image)
            if cw * ch < 0.5 * h * w:
                return None

            if self.debug:
                debug_img = image.copy()
                cv2.rectangle(debug_img, (x, y), (x + cw, y + ch), (0, 255, 0), 2)
                self.debug_images['roi'] = debug_img

            return (x, y, cw, ch)

        except Exception:
            return None

    def crop_to_roi(
        self,
        image: np.ndarray,
        roi_bounds: Tuple[int, int, int, int]
    ) -> np.ndarray:
        """
        Crop image to region of interest.

        Args:
            image: Input image
            roi_bounds: (x, y, width, height)

        Returns:
            Cropped image
        """
        x, y, w, h = roi_bounds
        return image[y:y+h, x:x+w].copy()

    def process_grayscale(self, image: np.ndarray) -> np.ndarray:
        """
        Simplified preprocessing that returns enhanced grayscale.

        Args:
            image: Input image

        Returns:
            Enhanced grayscale image
        """
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        cfg = self.preprocess_config

        # Apply bilateral filter
        filtered = cv2.bilateralFilter(
            gray,
            d=cfg.bilateral_d,
            sigmaColor=cfg.bilateral_sigma_color,
            sigmaSpace=cfg.bilateral_sigma_space
        )

        # Apply CLAHE
        clahe = cv2.createCLAHE(
            clipLimit=cfg.clahe_clip_limit,
            tileGridSize=(cfg.clahe_tile_size, cfg.clahe_tile_size)
        )
        enhanced = clahe.apply(filtered)

        return enhanced


def preprocess_image(
    image: np.ndarray,
    config: Optional[ChartConfig] = None
) -> PreprocessResult:
    """
    Convenience function to preprocess an image.

    Args:
        image: Input image (BGR format)
        config: Chart configuration (optional)

    Returns:
        PreprocessResult
    """
    preprocessor = Preprocessor(config=config)
    return preprocessor.process(image)


__all__ = ['Preprocessor', 'preprocess_image']
