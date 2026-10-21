"""What is running right now: Home Assistant states in, an ordered item list out.

Pure logic, no I/O, so it can be tested with plain dicts.
"""
from __future__ import annotations

import math
from datetime import datetime

from .sources import MISSING, Source

DONE_LINGER_SECONDS = 30 * 60
IMAGE_URL = "/api/image/{entity}?v={version}"


class DoneTracker:
    """Remembers when each source was *seen* finishing.

    The first value after startup never counts, so a printer that finished
    hours ago doesn't show "Done". A brief unknown/unavailable blip is skipped
    over, so it neither clears a Done nor fakes a new one.
    """

    def __init__(self) -> None:
        self._prev: dict[str, str] = {}
        self.done_at: dict[str, float] = {}

    def update(self, sources: list[Source], states: dict, now: float) -> dict[str, float]:
        for src in sources:
            state = _state(states, src.state)
            if state in MISSING:
                continue
            prev = self._prev.get(src.id)
            if not src.is_done(state):
                self.done_at.pop(src.id, None)
            elif prev is not None and not src.is_done(prev):
                self.done_at[src.id] = now
            self._prev[src.id] = state
        return self.done_at


def build_items(sources: list[Source], states: dict, now: float, done_at: dict[str, float]) -> list[dict]:
    """Done items first (they need you, newest first), then running ones, soonest finish first."""
    done, running = [], []
    for src in sources:
        state = _state(states, src.state)
        if src.is_active(state):
            running.append(_running_item(src, states, now))
        elif src.id in done_at and now - done_at[src.id] < DONE_LINGER_SECONDS:
            done.append((done_at[src.id], _done_item(src, states, state, done_at[src.id])))
    done.sort(key=lambda pair: -pair[0])
    running.sort(key=lambda it: it["ends_at"] if it["ends_at"] is not None else math.inf)
    return [item for _, item in done] + running


def _running_item(src: Source, states: dict, now: float) -> dict:
    ends_at = _timestamp(states, src.ends)
    seconds_left = None if ends_at is None else max(0, round(ends_at - now))
    pct = _number(states, src.progress)
    total = _number(states, src.total_minutes)
    if pct is None and total and seconds_left is not None:
        pct = 100 * (1 - seconds_left / (total * 60))
    stage = _state(states, src.stage)
    return {
        "id": src.id,
        "name": src.name,
        "status": "running",
        "done_at": None,
        "ends_at": ends_at,
        "seconds_left": seconds_left,
        "pct": None if pct is None else max(0, min(100, round(pct))),
        "detail": _pretty(stage if stage not in MISSING else _state(states, src.state)),
        "image": _image_url(src, states),
    }


def _done_item(src: Source, states: dict, state: str, done_at: float) -> dict:
    failed = state in src.failed
    return {
        "id": src.id,
        "name": src.name,
        "status": "failed" if failed else "done",
        "done_at": done_at,
        "ends_at": None,
        "seconds_left": None,
        "pct": 100,
        "detail": "Failed" if failed else "Done",
        "image": _image_url(src, states),
    }


def _image_url(src: Source, states: dict) -> str | None:
    if not src.image or src.image not in states:
        return None
    # The image entity's state changes when the picture does: use it to bust caches.
    return IMAGE_URL.format(entity=src.image, version=states[src.image]["state"])


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
