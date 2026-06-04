"""utils.image_utils: load + save + base64 roundtrips."""

import base64

import cv2
import numpy as np
import pytest

from utils.image_utils import encode_image_base64, load_image, save_image


def test_save_then_load_png_roundtrip(tmp_path):
    img = np.zeros((50, 60, 3), dtype=np.uint8)
    img[:, :, 1] = 200  # solid green block
    out = tmp_path / "roundtrip.png"
    assert save_image(img, out) is True
    reloaded = load_image(out)
    assert reloaded.shape == img.shape
    # PNG is lossless, so the green block must survive bit-exact.
    assert np.array_equal(reloaded, img)


def test_save_jpeg_path(tmp_path):
    img = np.full((40, 40, 3), 128, dtype=np.uint8)
    out = tmp_path / "roundtrip.jpg"
    assert save_image(img, out, quality=85) is True
    reloaded = load_image(out)
    assert reloaded.shape == img.shape


def test_load_missing_file_raises():
    with pytest.raises(ValueError):
        load_image("/tmp/does-not-exist-12345.png")


def test_encode_image_base64_is_decodable(tmp_path):
    img = np.full((20, 30, 3), 200, dtype=np.uint8)
    encoded = encode_image_base64(img)
    assert isinstance(encoded, str) and len(encoded) > 0
    # The base64 payload must decode back into a PNG buffer OpenCV can read.
    raw = base64.b64decode(encoded)
    decoded = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_UNCHANGED)
    assert decoded is not None
    assert decoded.shape[:2] == (20, 30)
