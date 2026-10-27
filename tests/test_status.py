from datetime import datetime, timezone

import pytest

from server.demo import SCENARIOS, demo_items
from server.sources import SOURCES
from server.status import COOL_TIMEOUT_SECONDS, COOLED_C, DONE_LINGER_SECONDS, Finish, FinishTracker, build_items

NOW = 1_800_000_000.0
PRINTER, MONO, WASHER, DRYER, DISHWASHER, SLOW_COOKER = SOURCES


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def states(**values) -> dict:
    """entity=state, or entity=(state, {attributes})."""
    out = {}
    for e, v in values.items():
        state, attrs = v if isinstance(v, tuple) else (v, {})
        out[e] = {"entity_id": e, "state": state, "attributes": attrs}
    return out


def run(src_states: dict, finished: dict | None = None, now: float = NOW) -> list[dict]:
    return build_items(SOURCES, src_states, now, finished or {})


CLEAR_ALL = "input_button.clear_finished"


def step(tracker: FinishTracker, now: float, **values) -> list[dict]:
    """Feed one set of HA states to the tracker and return what the screen shows."""
    s = states(**values)
    return run(s, tracker.update(SOURCES, s, now, CLEAR_ALL), now)


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


def test_unavailable_cover_image_is_no_image():
    (item,) = run(states(**{PRINTER.state: "running", PRINTER.image: "unavailable"}))
    assert item["image"] is None


def test_demo_uses_stand_in_print_when_cover_is_unavailable():
    real = {src.image: {"state": "unavailable", "attributes": {}} for src in SOURCES if src.image}
    items = demo_items("1", real, NOW)
    assert items[0]["image"].startswith("/api/image/demo.print")


# ---- finishing: general ------------------------------------------------------

def test_finished_before_startup_shows_nothing():
    assert step(FinishTracker(), NOW, **{PRINTER.state: "finish", PRINTER.cooldown: "60"}) == []


def test_unavailable_blip_keeps_finish_and_fakes_nothing():
    t = FinishTracker()
    step(t, NOW, **{DRYER.state: "running"})
    step(t, NOW, **{DRYER.state: "end"})
    step(t, NOW + 60, **{DRYER.state: "unavailable"})
    step(t, NOW + 120, **{DRYER.state: "end"})
    assert t.finished["dryer"].since == NOW


def test_new_cycle_clears_finish():
    t = FinishTracker()
    step(t, NOW, **{DRYER.state: "running"})
    step(t, NOW, **{DRYER.state: "end"})
    assert step(t, NOW + 60, **{DRYER.state: "running"})[0]["status"] == "running"
    assert "dryer" not in t.finished


# ---- printers: cooling down, then done ------------------------------------------

def test_print_finishing_hot_cools_down_then_done():
    t = FinishTracker()
    step(t, NOW, **{PRINTER.state: "running", PRINTER.cooldown: "55"})
    (item,) = step(t, NOW + 10, **{PRINTER.state: "finish", PRINTER.cooldown: "55"})
    assert item["status"] == "cooling" and item["detail"] == "Cooling down" and item["temp"] == 55
    (item,) = step(t, NOW + 600, **{PRINTER.state: "finish", PRINTER.cooldown: "40"})
    assert item["status"] == "cooling" and item["pct"] == 50  # 55 -> 25, halfway
    (item,) = step(t, NOW + 1200, **{PRINTER.state: "finish", PRINTER.cooldown: str(COOLED_C)})
    assert item["status"] == "done" and item["done_at"] == NOW + 1200


def test_done_lasts_30_minutes_from_when_it_cooled():
    t = FinishTracker()
    step(t, NOW, **{PRINTER.state: "running", PRINTER.cooldown: "55"})
    step(t, NOW, **{PRINTER.state: "finish", PRINTER.cooldown: "55"})
    step(t, NOW + 1000, **{PRINTER.state: "finish", PRINTER.cooldown: "24"})
    assert step(t, NOW + 1000 + DONE_LINGER_SECONDS - 1, **{PRINTER.state: "finish"}) != []
    assert step(t, NOW + 1000 + DONE_LINGER_SECONDS, **{PRINTER.state: "finish"}) == []


def test_print_picture_stays_through_cooling_and_done():
    t = FinishTracker()
    url = f"/api/image/{PRINTER.image}?v=pic1"
    step(t, NOW, **{PRINTER.state: "running", PRINTER.cooldown: "55", PRINTER.image: "pic1"})
    (item,) = step(t, NOW + 10, **{PRINTER.state: "finish", PRINTER.cooldown: "55", PRINTER.image: "unavailable"})
    assert item["status"] == "cooling" and item["image"] == url  # HA dropped it; we kept it
    (item,) = step(t, NOW + 600, **{PRINTER.state: "finish", PRINTER.cooldown: "24", PRINTER.image: "unavailable"})
    assert item["status"] == "done" and item["image"] == url


def test_cooling_gives_up_in_a_warm_room():
    t = FinishTracker()
    step(t, NOW, **{PRINTER.state: "running", PRINTER.cooldown: "55"})
    step(t, NOW, **{PRINTER.state: "finish", PRINTER.cooldown: "55"})
    (item,) = step(t, NOW + COOL_TIMEOUT_SECONDS, **{PRINTER.state: "finish", PRINTER.cooldown: "28"})
    assert item["status"] == "done"


def test_already_cool_print_is_done_straight_away():
    t = FinishTracker()
    step(t, NOW, **{PRINTER.state: "running", PRINTER.cooldown: "24"})
    (item,) = step(t, NOW, **{PRINTER.state: "finish", PRINTER.cooldown: "24"})
    assert item["status"] == "done"


def test_failed_print_is_failed_right_away():
    t = FinishTracker()
    step(t, NOW, **{PRINTER.state: "running", PRINTER.cooldown: "55"})
    (item,) = step(t, NOW, **{PRINTER.state: "failed", PRINTER.cooldown: "55"})
    assert item["status"] == "failed" and item["detail"] == "Failed"


# ---- washer: move to dryer --------------------------------------------------------

def test_washer_says_move_to_dryer_through_power_off():
    t = FinishTracker()
    step(t, NOW, **{WASHER.state: "running", DRYER.state: "power_off"})
    step(t, NOW, **{WASHER.state: "end", DRYER.state: "power_off"})
    # LG switches itself off 30 s later; hours later it still needs moving.
    (item,) = step(t, NOW + 5 * 3600, **{WASHER.state: "power_off", DRYER.state: "power_off"})
    assert item["status"] == "waiting" and item["detail"] == "Move to dryer"


def test_move_to_dryer_clears_when_dryer_starts():
    t = FinishTracker()
    step(t, NOW, **{WASHER.state: "running", DRYER.state: "power_off"})
    step(t, NOW, **{WASHER.state: "end", DRYER.state: "power_off"})
    items = step(t, NOW + 600, **{WASHER.state: "power_off", DRYER.state: "running"})
    assert [it["id"] for it in items] == ["dryer"]


def test_dryer_still_running_last_load_does_not_clear_move_to_dryer():
    t = FinishTracker()
    step(t, NOW, **{WASHER.state: "running", DRYER.state: "running"})
    step(t, NOW, **{WASHER.state: "end", DRYER.state: "running"})
    assert "washer" in t.finished  # dryer was already busy: the wash still needs moving
    step(t, NOW + 600, **{WASHER.state: "power_off", DRYER.state: "end"})
    assert "washer" in t.finished
    step(t, NOW + 900, **{WASHER.state: "power_off", DRYER.state: "running"})
    assert "washer" not in t.finished


# ---- dryer: done for 30 minutes ----------------------------------------------------

def test_dryer_done_survives_power_off_for_30_minutes():
    t = FinishTracker()
    step(t, NOW, **{DRYER.state: "running"})
    step(t, NOW, **{DRYER.state: "end"})
    (item,) = step(t, NOW + 30, **{DRYER.state: "power_off"})
    assert item["status"] == "done"
    assert step(t, NOW + DONE_LINGER_SECONDS, **{DRYER.state: "power_off"}) == []


# ---- timers (Stream Deck) ----------------------------------------------------------

def timer(seconds_left: float, duration: str = "2:00:00", state: str = "active"):
    return (state, {"finishes_at": iso(NOW + seconds_left), "duration": duration})


def test_running_timer_counts_down_with_progress():
    (item,) = step(FinishTracker(), NOW, **{DISHWASHER.state: timer(30 * 60)})
    assert item["status"] == "running" and item["seconds_left"] == 30 * 60 and item["pct"] == 75


def test_timer_running_out_is_done():
    t = FinishTracker()
    step(t, NOW, **{DISHWASHER.state: timer(60)})
    (item,) = step(t, NOW + 61, **{DISHWASHER.state: ("idle", {"duration": "2:00:00"})})
    assert item["status"] == "done" and item["name"] == "Dishwasher"


def test_cancelled_timer_shows_nothing():
    t = FinishTracker()
    step(t, NOW, **{SLOW_COOKER.state: timer(3600)})
    assert step(t, NOW + 60, **{SLOW_COOKER.state: ("idle", {})}) == []


# ---- clear buttons (Stream Deck) -------------------------------------------------

def test_clear_dryer_button_clears_only_the_dryer():
    t = FinishTracker()
    step(t, NOW, **{DRYER.state: "running", DISHWASHER.state: timer(60), "input_button.clear_dryer": "2026-01-01T00:00:00"})
    step(t, NOW + 61, **{DRYER.state: "end", DISHWASHER.state: ("idle", {}), "input_button.clear_dryer": "2026-01-01T00:00:00"})
    items = step(t, NOW + 90, **{DRYER.state: "power_off", DISHWASHER.state: ("idle", {}),
                                 "input_button.clear_dryer": iso(NOW + 90)})
    assert [it["id"] for it in items] == ["dishwasher"]


def test_clear_finished_button_clears_everything_finished():
    t = FinishTracker()
    before = {WASHER.state: "running", DRYER.state: "power_off", PRINTER.state: "running", CLEAR_ALL: "2026-01-01T00:00:00"}
    step(t, NOW, **before)
    step(t, NOW + 10, **{**before, WASHER.state: "end", PRINTER.state: "finish"})
    assert len(t.finished) == 2
    assert step(t, NOW + 20, **{**before, WASHER.state: "power_off", PRINTER.state: "finish", CLEAR_ALL: iso(NOW + 20)}) == []


def test_first_sight_of_a_button_is_not_a_press():
    t = FinishTracker()
    step(t, NOW, **{DRYER.state: "running"})
    step(t, NOW, **{DRYER.state: "end"})
    assert step(t, NOW + 5, **{DRYER.state: "end", "input_button.clear_dryer": iso(NOW)}) != []


# ---- order ------------------------------------------------------------------

def test_order_attention_then_cooling_then_soonest_finish():
    s = states(**{
        PRINTER.state: "finish", PRINTER.cooldown: "50",
        MONO.state: "running", MONO.ends: iso(NOW + 3600),
        WASHER.state: "power_off",
        DRYER.state: "running", DRYER.ends: iso(NOW + 600),
    })
    finished = {"p1s_color": Finish("cooling", NOW - 60, start_temp=60), "washer": Finish("waiting", NOW - 600)}
    assert [it["id"] for it in run(s, finished)] == ["washer", "p1s_color", "dryer", "p1s_mono"]


# ---- demos ------------------------------------------------------------------

@pytest.mark.parametrize("name", SCENARIOS)
def test_demo_item_counts(name):
    count, _ = SCENARIOS[name]
    assert len(demo_items(name, {}, NOW)) == count


@pytest.mark.parametrize("name", ["done", "failed", "waiting"])
def test_demo_finished_item_comes_first(name):
    assert demo_items(name, {}, NOW)[0]["status"] == name


def test_demo_cooling():
    item = demo_items("cooling", {}, NOW)[0]
    assert item["status"] == "cooling" and item["temp"] is not None


# ---- cameras ----------------------------------------------------------------

def test_printer_camera_only_while_available():
    s = states(**{PRINTER.state: "running", PRINTER.camera: "idle"})
    assert run(s)[0]["camera"] == f"/api/camera/{PRINTER.camera}"
    s = states(**{PRINTER.state: "running", PRINTER.camera: "unavailable"})
    assert run(s)[0]["camera"] is None


def test_side_cameras_skip_missing_ones():
    from server.sources import Camera
    from server.status import cameras
    cams = [Camera("camera.front", "Front"), Camera("camera.gone", "Gone")]
    assert cameras(cams, states(**{"camera.front": "streaming"})) == [
        {"id": "camera.front", "name": "Front", "url": "/api/camera/camera.front"}
    ]
