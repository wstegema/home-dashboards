"""Small, ready-to-draw thumbnails for low-memory screens (the CYD).

The CYD can't decode PNGs (not enough contiguous memory) or scale images (its
LVGL build has no transform support for RGB565). So the server does both: it
draws the picture at the exact size the screen shows it, and can send it as an
uncompressed BMP, which the device decodes with almost no memory.

The CYD shows the picture inside a ring, so `size` is the ring's inside
diameter. The background is pure black: the CYD is viewed from above, where its
panel washes any grey out to a pale blob. The model keeps its real colors and
brightness exactly (Bambu renders covers in the filament's color); a dark model
only gets a thin light outline so its shape shows on black.
"""
from __future__ import annotations

from functools import lru_cache
from io import BytesIO

from PIL import Image, ImageFilter, ImageStat

FORMATS = {"bmp": ("BMP", "image/bmp"), "png": ("PNG", "image/png")}
MAX_SIZE = 256
OUTLINE = (200, 200, 200)  # around dark models (black filament)
DARK_MODEL = 80  # average brightness (0-255) below which a model gets an outline


def sniff_type(data: bytes, fallback: str) -> str:
    """HA labels some PNG covers as image/jpeg; trust the bytes instead."""
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    return fallback


@lru_cache(maxsize=32)
def thumbnail(data: bytes, size: int, fmt: str) -> tuple[bytes, str]:
    """Draw `data` (any image) centered on black in a size x size square."""
    pil_format, mime = FORMATS[fmt]
    with Image.open(BytesIO(data)) as src:
        img = src.convert("RGBA")
    alpha = img.getchannel("A")
    # Crop to the model itself: print covers are mostly empty plate.
    bbox = alpha.getbbox()
    if bbox:
        img = img.crop(bbox)
        alpha = img.getchannel("A")
    # Fit the model's diagonal inside the ring, so no corner of it is cut off.
    scale = 0.92 * size / (img.width ** 2 + img.height ** 2) ** 0.5  # up or down
    img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    outline = _is_dark(img)
    square = Image.new("RGB", (size, size), (0, 0, 0))
    at = ((size - img.width) // 2, (size - img.height) // 2)
    if outline:
        width = max(1, round(size / 75))  # 1 px in the small rings, 2 px in the big one
        edge = Image.new("L", (size, size), 0)
        edge.paste(img.getchannel("A"), at)
        square.paste(OUTLINE, (0, 0), edge.filter(ImageFilter.MaxFilter(2 * width + 1)))
    square.paste(img, at, img)
    out = BytesIO()
    square.save(out, pil_format)
    return out.getvalue(), mime


def _is_dark(img: Image.Image) -> bool:
    """Whether the model is dark enough (e.g. black filament) to vanish on black."""
    mask = img.getchannel("A").point(lambda a: 255 if a > 128 else 0)
    return bool(mask.getbbox()) and ImageStat.Stat(img.convert("L"), mask).mean[0] < DARK_MODEL
