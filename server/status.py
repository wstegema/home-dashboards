"""What is running right now: Home Assistant states in, an ordered item list out.

Pure logic, no I/O, so it can be tested with plain dicts.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from .sources import MISSING, Source

DONE_LINGER_SECONDS = 30 * 60  # "Done" / "Failed" stay this long
COOLED_C = 25  # a printer bed at or below this is cool enough to take the print off
COOL_TIMEOUT_SECONDS = 3 * 3600  # call it done anyway if the room is too warm to get there
IMAGE_URL = "/api/image/{entity}?v={version}"
CAMERA_URL = "/api/camera/{entity}"


@dataclass
class Finish:
    """What a source is doing since it was seen finishing."""
    phase: str  # "cooling" | "done" | "failed" | "waiting"
    since: float  # when this phase started
    start_temp: float | None = None  # cooling only: temperature when cooling began
    other_stopped: bool = False  # waiting only: the other source has been seen not running
    image: str | None = None  # the print picture from while it ran (HA drops it at the end)


class FinishTracker:
    """Follows each source from the moment it is *seen* finishing.

    - cooldown sources (printers): cooling -> done once cool (or after a timeout)
    - wait_for sources (washer): waiting until the other source starts
    - others: done
    done / failed expire after DONE_LINGER_SECONDS. A new cycle clears everything.

    The first value after startup never counts, so something that finished
    hours ago shows nothing. unknown/unavailable blips are skipped over, and
    switching off (power_off) doesn't clear anything: LG machines do that by
    themselves 30 s after finishing.
    """

    def __init__(self) -> None:
        self._prev: dict[str, str] = {}
        self._ends: dict[str, float] = {}  # last known finish time while running
        self._images: dict[str, str] = {}  # last print picture URL while running
        self._buttons: dict[str, str] = {}  # last seen state of each clear button
        self.finished: dict[str, Finish] = {}

    def update(self, sources: list[Source], states: dict, now: float,
               clear_all: str | None = None) -> dict[str, Finish]:
        for src in sources:
            state = _state(states, src.state)
            if state in MISSING:
                continue
            prev = self._prev.get(src.id)
            self._prev[src.id] = state
            if src.is_active(state):
                self.finished.pop(src.id, None)  # a new cycle
                if (ends := _ends(src, states)) is not None:
                    self._ends[src.id] = ends
                if (image := _image_url(src, states)) is not None:
                    self._images[src.id] = image
            elif src.is_done(state) and prev is not None and not src.is_done(prev):
                # A timer that stops well before its finish time was cancelled, not done.
                cancelled = src.ends_attr is not None and self._ends.get(src.id, 0) > now + 5
                if not cancelled:
                    self.finished[src.id] = self._start(src, state, states, now)
                    self.finished[src.id].image = self._images.get(src.id)
                self._ends.pop(src.id, None)
                self._images.pop(src.id, None)

        # Clear buttons (Stream Deck): a press changes the button's state to the press time.
        for src in sources:
            for button in src.clear + ((clear_all,) if clear_all else ()):
                if self._pressed(button, states):
                    self.finished.pop(src.id, None)
        self._buttons.update({b: _state(states, b) for src in sources
                              for b in src.clear + ((clear_all,) if clear_all else ())
                              if _state(states, b) not in MISSING})

        by_id = {src.id: src for src in sources}
        for src_id, f in list(self.finished.items()):
            src = by_id[src_id]
            if f.phase == "cooling":
                temp = _number(states, src.cooldown)
                if (temp is not None and temp <= COOLED_C) or now - f.since >= COOL_TIMEOUT_SECONDS:
                    self.finished[src_id] = Finish("done", now, image=f.image)
            elif f.phase == "waiting":
                # Cleared when the other source *starts* a cycle, not if it was
                # already running the previous load when this one finished.
                other = by_id.get(src.wait_for)
                other_state = _state(states, other.state) if other else ""
                if other_state in MISSING:
                    continue
                if not other.is_active(other_state):
                    f.other_stopped = True
                elif f.other_stopped:
                    del self.finished[src_id]
            elif now - f.since >= DONE_LINGER_SECONDS:
                del self.finished[src_id]
        return self.finished

    def _pressed(self, button: str, states: dict) -> bool:
        state = _state(states, button)
        before = self._buttons.get(button)
        return state not in MISSING and before is not None and state != before

    @staticmethod
    def _start(src: Source, state: str, states: dict, now: float) -> Finish:
        if state in src.failed:
            return Finish("failed", now)
        if src.cooldown:
            temp = _number(states, src.cooldown)
            if temp is not None and temp > COOLED_C:
                return Finish("cooling", now, start_temp=temp)
        if src.wait_for:
            return Finish("waiting", now)
        return Finish("done", now)


def build_items(sources: list[Source], states: dict, now: float, finished: dict[str, Finish]) -> list[dict]:
    """Things that need you first (done, failed, waiting: newest first), then
    cooling, then running ones, soonest finish first."""
    attention, cooling, running = [], [], []
    for src in sources:
        state = _state(states, src.state)
        f = finished.get(src.id)
        if src.is_active(state):
            running.append(_running_item(src, states, now))
        elif f and f.phase == "cooling":
            cooling.append((f.since, _cooling_item(src, states, f)))
        elif f:
            attention.append((f.since, _finished_item(src, states, f)))
    attention.sort(key=lambda pair: -pair[0])
    cooling.sort(key=lambda pair: pair[0])
    running.sort(key=lambda it: it["ends_at"] if it["ends_at"] is not None else math.inf)
    return [it for _, it in attention] + [it for _, it in cooling] + running


def _base(src: Source, states: dict, status: str) -> dict:
    return {
        "id": src.id,
        "name": src.name,
        "status": status,
        "done_at": None,
        "ends_at": None,
        "seconds_left": None,
        "pct": None,
        "temp": None,
        "detail": "",
        "image": _image_url(src, states),
        "camera": None,
    }


def _running_item(src: Source, states: dict, now: float) -> dict:
    ends_at = _ends(src, states)
    seconds_left = None if ends_at is None else max(0, round(ends_at - now))
    pct = _number(states, src.progress)
    total = _number(states, src.total_minutes)
    if total is None and src.duration_attr:
        total = _hms_minutes(_attr(states, src.state, src.duration_attr))
    if pct is None and total and seconds_left is not None:
        pct = 100 * (1 - seconds_left / (total * 60))
    stage = _state(states, src.stage)
    return {
        **_base(src, states, "running"),
        "ends_at": ends_at,
        "seconds_left": seconds_left,
        "pct": None if pct is None else max(0, min(100, round(pct))),
        "detail": _pretty(stage if stage not in MISSING else _state(states, src.state)),
        "camera": _camera_url(src.camera, states),
    }


def _cooling_item(src: Source, states: dict, f: Finish) -> dict:
    """Ring fills as the bed cools from where it started down to COOLED_C."""
    temp = _number(states, src.cooldown)
    pct = None
    if temp is not None and f.start_temp and f.start_temp > COOLED_C:
        pct = max(0, min(100, round(100 * (f.start_temp - temp) / (f.start_temp - COOLED_C))))
    return {
        **_base(src, states, "cooling"),
        "image": _image_url(src, states) or f.image,
        "done_at": f.since,
        "pct": pct,
        "temp": None if temp is None else round(temp),
        "detail": "Cooling down",
    }


def _finished_item(src: Source, states: dict, f: Finish) -> dict:
    detail = {"failed": "Failed", "waiting": src.wait_text or "Done"}.get(f.phase, "Done")
    return {**_base(src, states, f.phase), "image": _image_url(src, states) or f.image,
            "done_at": f.since, "pct": 100, "detail": detail}


def cameras(cams: list, states: dict) -> list[dict]:
    """The side-column cameras that HA currently has a picture for."""
    return [{"id": c.entity, "name": c.name, "url": url} for c in cams if (url := _camera_url(c.entity, states))]


def _camera_url(entity: str | None, states: dict) -> str | None:
    if not entity or _state(states, entity) in MISSING:
        return None
    return CAMERA_URL.format(entity=entity)


def _image_url(src: Source, states: dict) -> str | None:
    if not src.image or states.get(src.image, {}).get("state") in (None, "unavailable", "unknown"):
        return None  # no print, or HA has no picture to give (e.g. after the print ends)
    # The image entity's state changes when the picture does: use it to bust caches.
    return IMAGE_URL.format(entity=src.image, version=states[src.image]["state"])


def _ends(src: Source, states: dict) -> float | None:
    if src.ends_attr:
        return _parse_time(_attr(states, src.state, src.ends_attr))
    return _timestamp(states, src.ends)


def _attr(states: dict, entity: str, name: str):
    st = states.get(entity)
    return (st.get("attributes") or {}).get(name) if st else None


def _hms_minutes(value) -> float | None:
    """'2:00:00' -> 120.0"""
    try:
        h, m, s = (int(part) for part in str(value).split(":"))
    except ValueError:
        return None
    return h * 60 + m + s / 60


def _parse_time(value) -> float | None:
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except ValueError:
        return None


def _state(states: dict, entity: str | None) -> str:
    st = states.get(entity) if entity else None
    return st["state"] if st else ""


def _number(states: dict, entity: str | None) -> float | None:
    try:
        return float(_state(states, entity))
    except ValueError:
        return None


def _timestamp(states: dict, entity: str | None) -> float | None:
    try:
        return datetime.fromisoformat(_state(states, entity)).timestamp()
    except ValueError:
        return None


def _pretty(state: str) -> str:
    return state.replace("_", " ").capitalize()
