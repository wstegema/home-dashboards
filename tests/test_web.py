from io import BytesIO

import httpx
from fastapi.testclient import TestClient
from PIL import Image

from server import web

client = TestClient(web.app)  # no `with`: the HA connection isn't started
_out = BytesIO()
Image.new("RGB", (4, 4), (255, 0, 0)).save(_out, "PNG")
PNG = _out.getvalue()


def test_demo_print_is_served_as_a_cyd_thumbnail():
    r = client.get("/api/image/demo.print?v=1&size=68&format=bmp")
    assert r.status_code == 200 and r.headers["content-type"] == "image/bmp"
    with Image.open(BytesIO(r.content)) as img:
        assert img.size == (68, 68)


def test_fetch_errors_hide_the_ha_url(monkeypatch):
    async def fail(entity_id):
        request = httpx.Request("GET", "http://ha/api/image_proxy/x?token=SECRET")
        raise httpx.HTTPStatusError("500", request=request, response=httpx.Response(500, request=request))

    monkeypatch.setattr(web.ha, "fetch_picture", fail)
    r = client.get("/api/image/image.printer_cover")
    assert r.status_code == 502
    assert "SECRET" not in r.text and "Home Assistant returned 500" in r.text


def test_last_picture_is_served_when_ha_has_none(monkeypatch):
    calls = []

    async def fetch(entity_id):
        calls.append(entity_id)
        if len(calls) > 1:
            raise LookupError("no picture")  # the print ended
        return PNG, "image/png"

    monkeypatch.setattr(web.ha, "fetch_picture", fetch)
    assert client.get("/api/image/image.p1_cover?v=1").status_code == 200
    r = client.get("/api/image/image.p1_cover?v=unavailable")
    assert r.status_code == 200 and r.content == PNG
