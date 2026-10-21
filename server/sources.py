"""The things the status dashboard watches. Add a device here and nowhere else.

Each source names the Home Assistant entities that say whether it is running,
when it finishes, and how far along it is.
"""
from __future__ import annotations

from dataclasses import dataclass

# States that mean "HA doesn't know right now". They never count as a change.
MISSING = frozenset({"", "unknown", "unavailable"})
# States that mean "switched off / nothing happening".
IDLE = frozenset({"power_off", "initial", "off", "idle", "offline"})


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    state: str  # entity whose state says running / done
    ends: str  # entity holding the finish time as an ISO timestamp
    done: frozenset[str]
    failed: frozenset[str] = frozenset()  # done states shown as failed (red)
    active: frozenset[str] | None = None  # None: anything not missing, idle or done
    progress: str | None = None  # entity with 0-100
    total_minutes: str | None = None  # entity with the cycle length, to work out progress
    stage: str | None = None  # entity with a more specific status while running
    image: str | None = None  # image.* entity: the print thumbnail
    camera: str | None = None  # camera.* entity: live view while it runs (detail view)

    def is_done(self, state: str) -> bool:
        return state in self.done

    def is_active(self, state: str) -> bool:
        if self.active is not None:
            return state in self.active
        return state not in MISSING and state not in IDLE and not self.is_done(state)


PRINTER_ACTIVE = frozenset({"running", "prepare", "pause", "slicing", "init"})


def bambu(id: str, name: str, prefix: str) -> Source:
    return Source(
        id, name,
        state=f"sensor.{prefix}_print_status",
        ends=f"sensor.{prefix}_end_time",
        done=frozenset({"finish", "failed"}),
        failed=frozenset({"failed"}),
        active=PRINTER_ACTIVE,
        progress=f"sensor.{prefix}_print_progress",
        stage=f"sensor.{prefix}_current_stage",
        image=f"image.{prefix}_cover_image",
        camera=f"camera.{prefix}_camera",
    )


def lg_thinq(id: str, name: str, prefix: str, done: set[str]) -> Source:
    # LG ThinQ's "remaining_time" sensor is actually the finish timestamp.
    return Source(
        id, name,
        state=f"sensor.{prefix}_current_status",
        ends=f"sensor.{prefix}_remaining_time",
        done=frozenset(done),
        total_minutes=f"sensor.{prefix}_total_time",
    )


SOURCES: list[Source] = [
    bambu("p1s_color", "P1S Color", "office_p1s_color"),
    bambu("p1s_mono", "P1S Mono", "p1s_01p00c5b1101239"),
    lg_thinq("washer", "Washer", "washer", {"end"}),
    lg_thinq("dryer", "Dryer", "kitchen_dryer", {"end", "wrinkle_care"}),
]


@dataclass(frozen=True)
class Camera:
    entity: str  # camera.* entity
    name: str


# Shown in a side column of the detail view, always (not just while something runs).
# Entity IDs: HA -> Settings -> Entities, search "camera.".
CAMERAS: list[Camera] = [
    Camera("camera.cat_cam", "Cat Cam"),
    Camera("camera.pan", "Pan"),
    Camera("camera.porch_cam", "Porch"),  # hidden while HA reports it unavailable
]
