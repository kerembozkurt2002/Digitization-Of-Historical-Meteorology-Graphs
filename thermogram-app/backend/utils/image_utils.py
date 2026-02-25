"""
Image utility functions.

Uses Pillow to load images (handles more formats than OpenCV),
then converts to OpenCV format for processing.
"""

import cv2
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Optional, Union


def load_image(path: Union[str, Path]) -> np.ndarray:
    """
    Load an image from file using Pillow (handles more formats including old TIFF).

    Args:
        path: Path to image file

    Returns:
        Image as numpy array in BGR format (OpenCV compatible)

    Raises:
        ValueError: If image cannot be loaded
    """
    path = Path(path)

    if not path.exists():
        raise ValueError(f"Image file not found: {path}")

    try:
        # Use Pillow to load image (handles old JPEG TIFF compression)
        with Image.open(path) as img:
            # Convert to RGB if necessary
            if img.mode == 'RGBA':
                # Remove alpha channel
                img = img.convert('RGB')
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            # Convert to numpy array
            rgb_array = np.array(img)

            # Convert RGB to BGR for OpenCV
            bgr_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)

            return bgr_array

    except Exception as e:
        raise ValueError(f"Could not load image {path}: {str(e)}")


def save_image(image: np.ndarray, path: Union[str, Path], quality: int = 95) -> bool:
    """
    Save an image to file.

    Args:
        image: Image as numpy array (BGR format)
        path: Output path
        quality: JPEG quality (1-100)

    Returns:
        True if successful
    """
    path = Path(path)

    try:
        # Determine format from extension
        ext = path.suffix.lower()

        if ext in ['.jpg', '.jpeg']:
            cv2.imwrite(str(path), image, [cv2.IMWRITE_JPEG_QUALITY, quality])
        elif ext == '.png':
            cv2.imwrite(str(path), image, [cv2.IMWRITE_PNG_COMPRESSION, 6])
        else:
            cv2.imwrite(str(path), image)

        return True

    except Exception as e:
        print(f"Error saving image: {e}")
        return False


def resize_image(image: np.ndarray, max_size: int = 2000) -> np.ndarray:
    """
    Resize image if it's larger than max_size while maintaining aspect ratio.

    Args:
        image: Input image
        max_size: Maximum dimension

    Returns:
        Resized image (or original if already small enough)
    """
    h, w = image.shape[:2]

    if max(h, w) <= max_size:
        return image

    if h > w:
        new_h = max_size
        new_w = int(w * (max_size / h))
    else:
        new_w = max_size
        new_h = int(h * (max_size / w))

    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)


def encode_image_base64(image: np.ndarray, format: str = 'png') -> str:
    """
    Encode image as base64 string.

    Args:
        image: Input image (BGR format)
        format: Output format ('png' or 'jpg')

    Returns:
        Base64 encoded string
    """
    import base64

    if format == 'jpg':
        _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 85])
    else:
        _, buffer = cv2.imencode('.png', image)

    return base64.b64encode(buffer).decode('utf-8')


def decode_image_base64(base64_string: str) -> np.ndarray:
    """
    Decode base64 string to image.

    Args:
        base64_string: Base64 encoded image

    Returns:
        Image as numpy array (BGR format)
    """
    import base64

    img_data = base64.b64decode(base64_string)
    np_arr = np.frombuffer(img_data, np.uint8)
    return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
