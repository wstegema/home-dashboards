from io import BytesIO

import httpx
from fastapi.testclient import TestClient
from PIL import Image

from server import web

client = TestClient(web.app)  # no `with`: the HA connection isn't started


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
