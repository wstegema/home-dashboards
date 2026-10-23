"""Fake scenarios so every layout can be checked with nothing running.

Each scenario builds fake HA states and runs them through the real status
logic, so demos exercise the same code as live data.
"""
from __future__ import annotations

from datetime import datetime

from .sources import SOURCES, Source
from .status import Finish, build_items

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

# Scenario name -> (how many sources run, and optionally one that has finished:
# (source id, phase)). Phases match status.Finish: done, failed, cooling, waiting.
SCENARIOS: dict[str, tuple[int, tuple[str, str] | None]] = {
    "0": (0, None),
    "1": (1, None),
    "2": (2, None),
    "3": (3, None),
    "4": (4, None),
    "5": (5, None),
    "6": (6, None),
    "8": (8, None),  # more than fit: pages
    "done": (4, ("p1s_color", "done")),
    "failed": (3, ("p1s_color", "failed")),
    "cooling": (3, ("p1s_color", "cooling")),
    "waiting": (4, ("washer", "waiting")),
}
COOLING_FROM, COOLING_NOW = 60, 41  # demo bed temperatures, °C


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
    count, special = SCENARIOS.get(name, (0, None))
    states = dict(real_states)
    by_id = {src.id: src for src in DEMO_SOURCES}

    def put(entity: str | None, value) -> None:
        if entity:
            states[entity] = {"entity_id": entity, "state": str(value), "attributes": {}}

    for src in DEMO_SOURCES:
        put(src.state, "idle")
    for src_id, minutes, pct in RUNNING[:count]:
        src = by_id[src_id]
        put(src.state, "running")
        put(src.stage, "printing")
        put(src.ends, datetime.fromtimestamp(now + minutes * 60).astimezone().isoformat())
        put(src.progress, pct)
        put(src.total_minutes, round(minutes / (1 - pct / 100)))
    finished = {}
    if special:
        src_id, phase = special
        src = by_id[src_id]
        put(src.state, next(iter(src.failed if phase == "failed" else src.done - src.failed)))
        put(src.cooldown, COOLING_NOW)
        finished[src_id] = Finish(phase, now - 3 * 60, start_temp=COOLING_FROM if phase == "cooling" else None)
    items = build_items(DEMO_SOURCES, states, now, finished)
    for item in items:
        if item["id"].startswith("p1s"):
            item["image"] = item["image"] or DEMO_PRINT
            if item["status"] == "running":
                item["camera"] = DEMO_CAMERA
    return items
