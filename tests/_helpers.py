"""Shared test helpers (not collected by pytest — leading underscore)."""

from __future__ import annotations

import numpy as np
from PIL import Image

from pylitehtml import RawResult

PNG_SIG = b"\x89PNG\r\n\x1a\n"
JPEG_SIG = b"\xff\xd8"


def is_png(out: bytes | RawResult) -> bool:
    return isinstance(out, bytes) and out[:8] == PNG_SIG


def is_jpeg(out: bytes | RawResult) -> bool:
    return isinstance(out, bytes) and out[:2] == JPEG_SIG


def to_image(result: bytes | RawResult) -> Image.Image:
    """RAW RawResult → PIL RGBA image."""
    assert isinstance(result, RawResult)
    return Image.frombytes("RGBA", (result.width, result.height), result.data)


def to_array(result: bytes | RawResult) -> np.ndarray:
    """RAW RawResult → (H, W, 4) uint8 array."""
    assert isinstance(result, RawResult)
    return np.frombuffer(result.data, np.uint8).reshape(result.height, result.width, 4)


def pixel(im: Image.Image, x: int, y: int) -> tuple[int, int, int, int]:
    p = im.getpixel((min(x, im.width - 1), min(y, im.height - 1)))
    assert isinstance(p, tuple)
    return (int(p[0]), int(p[1]), int(p[2]), int(p[3]) if len(p) > 3 else 255)


def is_red(im: Image.Image, x: int, y: int) -> bool:
    r, g, b, _ = pixel(im, x, y)
    return r > 200 and g < 80 and b < 80


def dark_pixels(im: Image.Image, thresh: int = 128) -> int:
    data = im.tobytes()  # RGBA, tightly packed
    return sum(1 for i in range(0, len(data), 4) if data[i] < thresh)


def has_dark(im: Image.Image, thresh: int = 100) -> bool:
    data = im.tobytes()
    return any(data[i] < thresh for i in range(0, len(data), 4))


def dark_mask(arr: np.ndarray, thresh: int = 110) -> np.ndarray:
    """Boolean mask of "ink" pixels (darker than background) from a to_array()."""
    return arr[:, :, 0] < thresh
