from datetime import datetime, timezone

import pytest

from server.demo import SCENARIOS, demo_items
from server.sources import SOURCES
from server.status import DONE_LINGER_SECONDS, DoneTracker, build_items

NOW = 1_800_000_000.0
PRINTER, MONO, WASHER, DRYER = SOURCES


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def states(**values: str) -> dict:
    return {e: {"entity_id": e, "state": v, "attributes": {}} for e, v in values.items()}


def run(src_states: dict, done_at: dict | None = None, now: float = NOW) -> list[dict]:
    return build_items(SOURCES, src_states, now, done_at or {})


# ---- active / done rules ---------------------------------------------------

@pytest.mark.parametrize("status", ["running", "prepare", "pause", "slicing", "init"])
def test_printer_active_states(status):
    items = run(states(**{PRINTER.state: status}))
    assert [it["id"] for it in items] == ["p1s_color"]


@pytest.mark.parametrize("status", ["idle", "offline", "finish", "failed", "unknown", ""])
def test_printer_not_active(status):
    assert run(states(**{PRINTER.state: status})) == []


@pytest.mark.parametrize("status", ["power_off", "initial", "unavailable", "unknown", "end"])
def test_washer_not_active(status):
    assert run(states(**{WASHER.state: status})) == []


@pytest.mark.parametrize("status", ["running", "rinsing", "spinning", "detecting"])
def test_washer_any_other_state_is_active(status):
    assert [it["id"] for it in run(states(**{WASHER.state: status}))] == ["washer"]


def test_dryer_wrinkle_care_is_done():
    assert DRYER.is_done("wrinkle_care")
    assert not WASHER.is_done("wrinkle_care")


# ---- time left and progress -------------------------------------------------

def test_printer_progress_and_time_left():
    (item,) = run(states(**{
        PRINTER.state: "running",
        PRINTER.ends: iso(NOW + 47 * 60),
        PRINTER.progress: "62",
        PRINTER.stage: "printing",
    }))
    assert item["seconds_left"] == 47 * 60
    assert item["pct"] == 62
    assert item["detail"] == "Printing"
    assert item["status"] == "running"


def test_laundry_progress_from_total_time():
    (item,) = run(states(**{
        WASHER.state: "running",
        WASHER.ends: iso(NOW + 15 * 60),
        WASHER.total_minutes: "60",
    }))
    assert item["pct"] == 75


def test_missing_end_time():
    (item,) = run(states(**{WASHER.state: "running", WASHER.ends: "unknown"}))
    assert item["ends_at"] is None and item["seconds_left"] is None and item["pct"] is None


def test_cover_image_url_changes_with_picture():
    s = states(**{PRINTER.state: "running", PRINTER.image: "2026-10-16T10:00:00"})
    (item,) = run(s)
    assert item["image"] == f"/api/image/{PRINTER.image}?v=2026-10-16T10:00:00"


# ---- done tracking ----------------------------------------------------------

def test_finished_before_startup_shows_nothing():
    tracker = DoneTracker()
    s = states(**{PRINTER.state: "finish"})
    assert run(s, tracker.update(SOURCES, s, NOW)) == []


def test_seen_finishing_shows_done_for_30_minutes():
    tracker = DoneTracker()
    tracker.update(SOURCES, states(**{PRINTER.state: "running"}), NOW)
    s = states(**{PRINTER.state: "finish"})
    done_at = tracker.update(SOURCES, s, NOW + 10)
    (item,) = run(s, done_at, NOW + 10)
    assert item["status"] == "done" and item["detail"] == "Done" and item["pct"] == 100
    assert run(s, done_at, NOW + 10 + DONE_LINGER_SECONDS - 1) != []
    assert run(s, done_at, NOW + 10 + DONE_LINGER_SECONDS) == []


def test_failed_print_is_failed():
    tracker = DoneTracker()
    tracker.update(SOURCES, states(**{PRINTER.state: "running"}), NOW)
    s = states(**{PRINTER.state: "failed"})
    (item,) = run(s, tracker.update(SOURCES, s, NOW))
    assert item["status"] == "failed" and item["detail"] == "Failed"


def test_turning_off_clears_done():
    tracker = DoneTracker()
    tracker.update(SOURCES, states(**{WASHER.state: "running"}), NOW)
    tracker.update(SOURCES, states(**{WASHER.state: "end"}), NOW)
    s = states(**{WASHER.state: "power_off"})
    assert run(s, tracker.update(SOURCES, s, NOW + 60)) == []


def test_unavailable_blip_keeps_done_and_fakes_nothing():
    tracker = DoneTracker()
    tracker.update(SOURCES, states(**{PRINTER.state: "running"}), NOW)
    tracker.update(SOURCES, states(**{PRINTER.state: "finish"}), NOW)
    tracker.update(SOURCES, states(**{PRINTER.state: "unavailable"}), NOW + 60)
    done_at = tracker.update(SOURCES, states(**{PRINTER.state: "finish"}), NOW + 120)
    assert done_at == {"p1s_color": NOW}


# ---- order ------------------------------------------------------------------

def test_done_first_then_soonest_finish_then_no_end_time():
    s = states(**{
        PRINTER.state: "finish",
        MONO.state: "running", MONO.ends: iso(NOW + 3600),
        WASHER.state: "running", WASHER.ends: iso(NOW + 600),
        DRYER.state: "running",
    })
    items = run(s, {"p1s_color": NOW - 60})
    assert [it["id"] for it in items] == ["p1s_color", "washer", "p1s_mono", "dryer"]


# ---- demos ------------------------------------------------------------------

@pytest.mark.parametrize("name", SCENARIOS)
def test_demo_item_counts(name):
    count, _ = SCENARIOS[name]
    assert len(demo_items(name, {}, NOW)) == count


def test_demo_done_and_failed_come_first():
    assert demo_items("done", {}, NOW)[0]["status"] == "done"
    assert demo_items("failed", {}, NOW)[0]["status"] == "failed"
