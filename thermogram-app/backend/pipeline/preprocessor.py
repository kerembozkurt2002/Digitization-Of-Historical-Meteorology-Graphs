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

            # Step 2: Denoise
            denoised = self._denoise(normalized)

            # Step 3: Enhance contrast
            enhanced = self._enhance_contrast(denoised)

            # Step 4: Detect ROI (optional)
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
