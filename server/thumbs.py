"""Small, ready-to-draw thumbnails for low-memory screens (the CYD).

The CYD can't decode PNGs (not enough contiguous memory) or scale images (its
LVGL build has no transform support for RGB565). So the server does both: it
fits the picture into a square of the exact size the screen draws, on black,
and can send it as an uncompressed BMP, which the device decodes with almost
no memory.
"""
from __future__ import annotations

from functools import lru_cache
from io import BytesIO

from PIL import Image

FORMATS = {"bmp": ("BMP", "image/bmp"), "png": ("PNG", "image/png")}
MAX_SIZE = 256


def sniff_type(data: bytes, fallback: str) -> str:
    """HA labels some PNG covers as image/jpeg; trust the bytes instead."""
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    return fallback


@lru_cache(maxsize=32)
def thumbnail(data: bytes, size: int, fmt: str) -> tuple[bytes, str]:
    """Fit `data` (any image) into a size x size square on black."""
    pil_format, mime = FORMATS[fmt]
    with Image.open(BytesIO(data)) as src:
        img = src.convert("RGBA")
    # Crop to the model itself: print covers are mostly empty plate.
    bbox = img.getchannel("A").getbbox()
    if bbox:
        pad = max(bbox[2] - bbox[0], bbox[3] - bbox[1]) // 20
        img = img.crop((max(0, bbox[0] - pad), max(0, bbox[1] - pad),
                        min(img.width, bbox[2] + pad), min(img.height, bbox[3] + pad)))
    scale = size / max(img.width, img.height)  # up or down: a cropped model may be small
    img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    square = Image.new("RGB", (size, size), (0, 0, 0))
    square.paste(img, ((size - img.width) // 2, (size - img.height) // 2), img)
    out = BytesIO()
    square.save(out, pil_format)
    return out.getvalue(), mime
