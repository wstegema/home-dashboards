"""Small, ready-to-draw thumbnails for low-memory screens (the CYD).

The CYD can't decode PNGs (not enough contiguous memory) or scale images (its
LVGL build has no transform support for RGB565). So the server does both: it
draws the picture at the exact size the screen shows it, and can send it as an
uncompressed BMP, which the device decodes with almost no memory.

The CYD shows the picture inside a ring, so `size` is the ring's inside
diameter: the model sits on a dark round plate that fills the ring, the corners
outside it are black (the ring is drawn over them), and dark models are
brightened so they don't vanish on the black screen.
"""
from __future__ import annotations

from functools import lru_cache
from io import BytesIO

from PIL import Image, ImageDraw, ImageEnhance, ImageStat

FORMATS = {"bmp": ("BMP", "image/bmp"), "png": ("PNG", "image/png")}
MAX_SIZE = 256
PLATE = (34, 34, 34)  # the round plate behind the model; a step up from the black screen
MIN_BRIGHTNESS = 120  # average brightness (0-255) a model is lifted to if darker
MAX_LIFT = 3.0


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
    img = _lift_dark(img)
    square = Image.new("RGB", (size, size), (0, 0, 0))
    ImageDraw.Draw(square).ellipse((0, 0, size - 1, size - 1), fill=PLATE)
    square.paste(img, ((size - img.width) // 2, (size - img.height) // 2), img)
    out = BytesIO()
    square.save(out, pil_format)
    return out.getvalue(), mime


def _lift_dark(img: Image.Image) -> Image.Image:
    """Brighten a dark model (e.g. black filament) until it reads on a dark screen."""
    mask = img.getchannel("A").point(lambda a: 255 if a > 128 else 0)
    if not mask.getbbox():
        return img
    brightness = ImageStat.Stat(img.convert("L"), mask).mean[0]
    if brightness >= MIN_BRIGHTNESS:
        return img
    lift = min(MAX_LIFT, MIN_BRIGHTNESS / max(brightness, 1))
    lit = ImageEnhance.Brightness(img.convert("RGB")).enhance(lift)
    lit.putalpha(img.getchannel("A"))
    return lit
