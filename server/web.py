"""HTTP: JSON for the screens, plus the static UI files in web/.

The server never builds HTML. Pages live in web/ and only read /api/status.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .demo import SCENARIOS, demo_cameras, demo_items
from .ha import HomeAssistant
from .sources import CAMERAS, CLEAR_ALL, SOURCES
from .thumbs import FORMATS, MAX_SIZE, sniff_type, thumbnail
from .status import FinishTracker, build_items, cameras

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("server")

HEARTBEAT_SECONDS = 15  # resend at least this often, even if nothing changed
SETTLE_SECONDS = 0.3  # bundle a burst of HA changes into one push

ha = HomeAssistant(config.HA_URL, config.HA_TOKEN)
tracker = FinishTracker()


async def track_done() -> None:
    """Watch every change, even with no screen open, so no finish is missed."""
    while True:
        await ha.wait_change()
        tracker.update(SOURCES, ha.states, time.time(), CLEAR_ALL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = []
    if ha.token:
        tasks = [asyncio.create_task(ha.run_forever()), asyncio.create_task(track_done())]
    else:
        log.warning("HA_TOKEN not set: only ?demo= data is available")
    yield
    for task in tasks:
        task.cancel()


app = FastAPI(title="home-dashboards", lifespan=lifespan)


def status(demo: str | None) -> dict:
    now = time.time()
    if demo is not None:
        if demo not in SCENARIOS:
            raise HTTPException(404, f"no demo '{demo}'; try one of {list(SCENARIOS)}")
        items, cams = demo_items(demo, ha.states, now), demo_cameras()
    else:
        items = build_items(SOURCES, ha.states, now, tracker.update(SOURCES, ha.states, now, CLEAR_ALL))
        cams = cameras(CAMERAS, ha.states)
    return {"now": now, "tz": ha.time_zone, "connected": ha.connected, "demo": demo, "items": items, "cameras": cams}


@app.get("/api/status")
def api_status(demo: str | None = None) -> dict:
    return status(demo)


@app.get("/api/status/stream")
async def api_status_stream(request: Request, demo: str | None = None):
    status(demo)  # 404 before streaming starts

    async def events():
        last = None
        while not await request.is_disconnected():
            data = status(demo)
            # "now" and the countdowns move every call; only push when something else changed.
            key = {**data, "now": None, "items": [{**it, "seconds_left": None} for it in data["items"]]}
            if key != last:
                last = key
                yield f"data: {json.dumps(data)}\n\n"
            try:
                if demo is None:
                    await asyncio.wait_for(ha.wait_change(), HEARTBEAT_SECONDS)
                    await asyncio.sleep(SETTLE_SECONDS)
                else:
                    await asyncio.sleep(HEARTBEAT_SECONDS)
            except asyncio.TimeoutError:
                last = None  # heartbeat: send even if unchanged

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-store"})


@app.get("/api/demos")
def api_demos() -> list[str]:
    return list(SCENARIOS)


@app.get("/api/image/{entity_id}")
async def api_image(entity_id: str, size: int | None = None, format: str = "png"):
    """The picture of an image.*/camera.* entity. With ?size=N it is fitted into an
    N x N square; &format=bmp sends it uncompressed (for the CYD)."""
    if not entity_id.startswith(("image.", "camera.")):
        raise HTTPException(400, "only image.* and camera.* entities")
    if size is not None and not 8 <= size <= MAX_SIZE:
        raise HTTPException(400, f"size must be 8-{MAX_SIZE}")
    if format not in FORMATS:
        raise HTTPException(400, f"format must be one of {list(FORMATS)}")
    try:
        content, content_type = await ha.fetch_picture(entity_id)
    except LookupError as e:
        raise HTTPException(404, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"fetch failed: {e}") from e
    if size is not None:
        content, content_type = thumbnail(content, size, format)
    else:
        content_type = sniff_type(content, content_type)
    return Response(content, media_type=content_type, headers={"Cache-Control": "max-age=300"})


@app.get("/api/camera/{entity_id}")
async def api_camera(entity_id: str):
    if not entity_id.startswith("camera."):
        raise HTTPException(400, "only camera.* entities")
    try:
        content, content_type = await ha.fetch_camera(entity_id)
    except LookupError as e:
        raise HTTPException(404, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"fetch failed: {e}") from e
    return Response(content, media_type=content_type, headers={"Cache-Control": "no-store"})


@app.get("/healthz")
def healthz() -> dict:
    return {"ha_connected": ha.connected, "entities": len(ha.states)}


@app.get("/")
def root():
    return RedirectResponse("/status/")


# Static UI. Mounted last so the API routes above win.
app.mount("/shared", StaticFiles(directory=config.WEB_DIR / "shared"), name="shared")
app.mount("/status", StaticFiles(directory=config.WEB_DIR / "status", html=True), name="status")
app.mount("/preview", StaticFiles(directory=config.WEB_DIR / "preview", html=True), name="preview")
