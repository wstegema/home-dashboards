from io import BytesIO

from PIL import Image

from server.thumbs import PLATE, sniff_type, thumbnail


def png(w: int, h: int, color=(255, 128, 0, 255)) -> bytes:
    out = BytesIO()
    Image.new("RGBA", (w, h), color).save(out, "PNG")
    return out.getvalue()


def test_bmp_is_exact_square_size():
    data, mime = thumbnail(png(512, 300), 64, "bmp")
    assert mime == "image/bmp" and data[:2] == b"BM"
    with Image.open(BytesIO(data)) as img:
        assert img.size == (64, 64) and img.mode == "RGB"


def test_picture_sits_on_a_round_plate():
    data, _ = thumbnail(png(200, 100), 64, "png")
    with Image.open(BytesIO(data)) as img:
        assert img.getpixel((32, 32)) == (255, 128, 0)  # picture in the middle
        assert img.getpixel((32, 4)) == PLATE  # plate above it, inside the circle
        assert img.getpixel((1, 1)) == (0, 0, 0)  # corners outside the plate are black


def test_transparent_areas_show_the_plate():
    data, _ = thumbnail(png(64, 64, (255, 255, 255, 0)), 32, "png")
    with Image.open(BytesIO(data)) as img:
        assert img.getpixel((16, 16)) == PLATE


def test_dark_models_are_brightened():
    data, _ = thumbnail(png(100, 100, (30, 30, 30, 255)), 64, "png")
    with Image.open(BytesIO(data)) as img:
        r, g, b = img.getpixel((32, 32))
        assert 80 <= r == g == b  # lifted (3x at most) so it reads on black


def test_bright_models_keep_their_colors():
    data, _ = thumbnail(png(100, 100, (255, 128, 0, 255)), 64, "png")
    with Image.open(BytesIO(data)) as img:
        assert img.getpixel((32, 32)) == (255, 128, 0)


def test_sniff_type_trusts_bytes_over_label():
    assert sniff_type(png(4, 4), "image/jpeg") == "image/png"
    assert sniff_type(b"\xff\xd8\xff", "image/png") == "image/jpeg"


def test_crops_to_the_model_before_fitting():
    img = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
    img.paste((255, 0, 0, 255), (180, 180, 220, 220))  # small model in a big empty plate
    out = BytesIO()
    img.save(out, "PNG")
    data, _ = thumbnail(out.getvalue(), 64, "png")
    with Image.open(BytesIO(data)) as thumb:
        assert thumb.getpixel((14, 32)) == (255, 0, 0)  # the model now fills the plate
