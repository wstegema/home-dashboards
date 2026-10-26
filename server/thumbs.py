"""Small, ready-to-draw thumbnails for low-memory screens (the CYD).

The CYD can't decode PNGs (not enough contiguous memory) or scale images (its
LVGL build has no transform support for RGB565). So the server does both: it
draws the picture at the exact size the screen shows it, and can send it as an
uncompressed BMP, which the device decodes with almost no memory.

The CYD shows the picture inside a ring, so `size` is the ring's inside
diameter: the model sits on a dark round plate that fills the ring, the corners
outside it are black (the ring is drawn over them). The model keeps its real
color: a dark model gets a light plate so black reads as black, and a white
model's highlights are pushed back to white (shrinking blends its shading to grey).
"""
from __future__ import annotations

from functools import lru_cache
from io import BytesIO

from PIL import Image, ImageDraw, ImageStat

FORMATS = {"bmp": ("BMP", "image/bmp"), "png": ("PNG", "image/png")}
MAX_SIZE = 256
PLATE = (34, 34, 34)  # behind light/colored models; a step up from the black screen
PLATE_LIGHT = (150, 150, 150)  # behind dark models (black filament)
DARK_MODEL = 80  # average brightness (0-255) below which a model counts as dark
WHITE_POINT = 245  # light models: the brightest 5% of pixels are scaled up to this
LIGHT_GAMMA = 0.7  # light models: midtone lift (1 = none)
NEUTRAL_SATURATION = 40  # white/grey models (0-255 saturation) get the white restore


def sniff_type(data: bytes, fallback: str) -> str:
    """HA labels some PNG covers as image/jpeg; trust the bytes instead."""
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    return fallback


@lru_cache(maxsize=32)
def thumbnail(data: bytes, size: int, fmt: str) -> tuple[bytes, str]:
    """Draw `data` (any image) on a round plate in a size x size square."""
    pil_format, mime = FORMATS[fmt]
    with Image.open(BytesIO(data)) as src:
        img = src.convert("RGBA")
    alpha = img.getchannel("A")
    # Crop to the model itself: print covers are mostly empty plate.
    bbox = alpha.getbbox()
    if bbox:
        img = img.crop(bbox)
        alpha = img.getchannel("A")
    # Fit the model's diagonal inside the plate, so no corner of it is cut off.
    scale = 0.92 * size / (img.width ** 2 + img.height ** 2) ** 0.5  # up or down
    img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    img, plate = _for_small_screen(img)
    square = Image.new("RGB", (size, size), (0, 0, 0))
    ImageDraw.Draw(square).ellipse((0, 0, size - 1, size - 1), fill=plate)
    square.paste(img, ((size - img.width) // 2, (size - img.height) // 2), img)
    out = BytesIO()
    square.save(out, pil_format)
    return out.getvalue(), mime


def _for_small_screen(img: Image.Image) -> tuple[Image.Image, tuple[int, int, int]]:
    """Pick the plate for the model and restore a light model's highlights."""
    mask = img.getchannel("A").point(lambda a: 255 if a > 128 else 0)
    if not mask.getbbox():
        return img, PLATE
    gray = img.convert("L")
    if ImageStat.Stat(gray, mask).mean[0] < DARK_MODEL:
        return img, PLATE_LIGHT
    if ImageStat.Stat(img.convert("HSV").getchannel("S"), mask).mean[0] > NEUTRAL_SATURATION:
        return img, PLATE  # colored filament: keep its color exactly
    hist = gray.histogram(mask)
    total, seen, top = sum(hist), 0, 255
    for level in range(255, -1, -1):  # brightness of the brightest 5%
        seen += hist[level]
        if seen >= total * 0.05:
            top = level
            break
    gain = min(1.5, max(1.0, WHITE_POINT / max(top, 1)))
    # Highlights to white, then lift the midtones: shading between small details
    # otherwise averages out to grey at this size.
    curve = [min(255, round(255 * (min(255, v * gain) / 255) ** LIGHT_GAMMA)) for v in range(256)]
    lit = img.convert("RGB").point(curve * 3)
    lit.putalpha(img.getchannel("A"))
    return lit, PLATE
