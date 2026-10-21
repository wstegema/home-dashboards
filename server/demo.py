"""Fake scenarios so every layout can be checked with nothing running.

Each scenario builds fake HA states and runs them through the real status
logic, so demos exercise the same code as live data.
"""
from __future__ import annotations

from datetime import datetime

from .sources import SOURCES, Source
from .status import build_items

# Made-up timers that only exist in demos, to fill the bigger layouts.
EXTRA = [
    Source(f"timer{n}", f"Timer {n}", state=f"demo.timer{n}", ends=f"demo.timer{n}_ends",
           done=frozenset({"end"}), total_minutes=f"demo.timer{n}_total")
    for n in range(5, 9)
]
DEMO_SOURCES = SOURCES + EXTRA

# (source id, minutes left, percent done), in the order they get switched on.
RUNNING = [
    ("p1s_color", 47, 62),
    ("p1s_mono", 95, 20),
    ("washer", 12, 85),
    ("dryer", 150, 15),
    ("timer5", 185, 5),
    ("timer6", 8, 93),
    ("timer7", 64, 40),
    ("timer8", 230, 2),
]

# Scenario name -> (how many sources run, what happens to the first one).
SCENARIOS: dict[str, tuple[int, str | None]] = {
    "0": (0, None),
    "1": (1, None),
    "2": (2, None),
    "3": (3, None),
    "4": (4, None),
    "5": (5, None),
    "6": (6, None),
    "8": (8, None),  # more than fit: pages
    "done": (4, "finish"),
    "failed": (3, "failed"),
}


# Placeholder pictures (web/shared/demo/) so the media layout can be checked without HA.
DEMO_CAMERA = "/shared/demo/camera.svg"
DEMO_PRINT = "/shared/demo/print.svg"


def demo_cameras() -> list[dict]:
    return [
        {"id": "camera.demo_front", "name": "Front door", "url": DEMO_CAMERA},
        {"id": "camera.demo_garage", "name": "Garage", "url": DEMO_CAMERA},
    ]


def demo_items(name: str, real_states: dict, now: float) -> list[dict]:
    """Items for a scenario. Real states are kept so printer cover images still resolve."""
    count, first_ends_as = SCENARIOS.get(name, (0, None))
    states = dict(real_states)
    by_id = {src.id: src for src in DEMO_SOURCES}

    def put(entity: str | None, value) -> None:
        if entity:
            states[entity] = {"entity_id": entity, "state": str(value), "attributes": {}}

    for src in DEMO_SOURCES:
        put(src.state, "idle")
    done_at = {}
    for n, (src_id, minutes, pct) in enumerate(RUNNING[:count]):
        src = by_id[src_id]
        put(src.state, "running")
        put(src.stage, "printing")
        put(src.ends, datetime.fromtimestamp(now + minutes * 60).astimezone().isoformat())
        put(src.progress, pct)
        put(src.total_minutes, round(minutes / (1 - pct / 100)))
        if n == 0 and first_ends_as:
            put(src.state, first_ends_as)
            done_at[src.id] = now - 3 * 60
    items = build_items(DEMO_SOURCES, states, now, done_at)
    for item in items:
        if item["id"].startswith("p1s"):
            item["image"] = item["image"] or DEMO_PRINT
            if item["status"] == "running":
                item["camera"] = DEMO_CAMERA
    return items
