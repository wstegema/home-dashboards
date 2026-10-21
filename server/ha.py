"""The one Home Assistant connection every screen shares.

Keeps every entity's latest state in memory and wakes waiters on any change.
"""
from __future__ import annotations

import asyncio
import json
import logging

import httpx
import websockets

log = logging.getLogger(__name__)


class HomeAssistant:
    def __init__(self, url: str, token: str) -> None:
        self.url = url
        self.token = token
        self.states: dict[str, dict] = {}
        self.time_zone: str | None = None
        self.connected = False
        self._changed = asyncio.Event()

    async def wait_change(self) -> None:
        """Returns on the next state or connection change."""
        await self._changed.wait()

    def _notify(self) -> None:
        # Swap in a fresh event so every current waiter wakes exactly once.
        event, self._changed = self._changed, asyncio.Event()
        event.set()

    async def run_forever(self) -> None:
        delay = 1
        while True:
            try:
                await self._session()
                delay = 1
            except asyncio.CancelledError:
                raise
            except Exception as e:  # network, auth, protocol: log and retry
                log.warning("Home Assistant connection lost: %s", e)
            if self.connected:
                self.connected = False
                self._notify()
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)

    async def _session(self) -> None:
        ws_url = "ws" + self.url.removeprefix("http") + "/api/websocket"  # http->ws, https->wss
        async with websockets.connect(ws_url, max_size=None) as ws:
            await ws.recv()  # auth_required
            await ws.send(json.dumps({"type": "auth", "access_token": self.token}))
            reply = json.loads(await ws.recv())
            if reply.get("type") != "auth_ok":
                raise RuntimeError(f"auth failed: {reply.get('message', reply.get('type'))}")

            # Subscribe first so no change between the two is lost.
            await ws.send(json.dumps({"id": 1, "type": "subscribe_events", "event_type": "state_changed"}))
            await ws.send(json.dumps({"id": 2, "type": "get_states"}))
            await ws.send(json.dumps({"id": 3, "type": "get_config"}))

            async for raw in ws:
                self._handle(json.loads(raw))

    def _handle(self, msg: dict) -> None:
        if msg.get("type") == "event":
            data = msg["event"]["data"]
            if data.get("new_state") is None:
                self.states.pop(data["entity_id"], None)
            else:
                self.states[data["entity_id"]] = data["new_state"]
            self._notify()
        elif msg.get("type") == "result":
            if not msg.get("success"):
                log.warning("request %s failed: %s", msg.get("id"), msg.get("error"))
            elif msg["id"] == 2:
                self.states = {s["entity_id"]: s for s in msg["result"]}
                self.connected = True
                log.info("connected to Home Assistant at %s (%d entities)", self.url, len(self.states))
                self._notify()
            elif msg["id"] == 3:
                self.time_zone = msg["result"].get("time_zone")

    async def fetch_picture(self, entity_id: str) -> tuple[bytes, str]:
        """The picture of an image.* or camera.* entity, fetched with the token."""
        state = self.states.get(entity_id)
        path = state and state.get("attributes", {}).get("entity_picture")
        if not path:
            raise LookupError(f"{entity_id} has no picture")
        return await self._get(path)

    async def fetch_camera(self, entity_id: str) -> tuple[bytes, str]:
        """A current snapshot from a camera.* entity."""
        if entity_id not in self.states:
            raise LookupError(f"{entity_id} not found")
        return await self._get(f"/api/camera_proxy/{entity_id}")

    async def _get(self, path: str) -> tuple[bytes, str]:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(self.url + path, headers={"Authorization": f"Bearer {self.token}"})
            r.raise_for_status()
            return r.content, r.headers.get("content-type", "image/jpeg")
