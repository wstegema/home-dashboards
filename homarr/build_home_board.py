"""Builds the Homarr 'home' board (sections + items) and saves it in one call.

Talks to Homarr through ../unraid-management/tools/mcpc.py (which holds the API key).
    python -I build_home_board.py [--dry]
Saving replaces every section and item on the board, so edit GROUPS here, not in Homarr.
Each group is a titled section; tiles are packed left-to-right, top-to-bottom
for both the desktop (12 columns) and phone (3 columns) layouts.
"""
import json
import random
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "unraid-management" / "tools"))
from mcpc import C  # noqa: E402

BOARD = "home"
HA = "onboarding_integration_2eafbcb4521075fb1e161dfaa9ad39aa"
UNRAID = "onboarding_integration_886047f00b93cab6d6ddb017b88d8ea8"
PIHOLE = "onboarding_integration_636cdbde5983537bddc0a624e98d4385"
APP = {
    "Home Assistant": "onboarding_app_2eafbcb4521075fb1e161dfaa9ad39aa",
    "Bambuddy": "onboarding_app_07e054882a90b7032f4396a51e5572aa",
    "Immich": "zg5hroqi8lt88cjzth0l83vq",
    "File Browser": "tmuzanr9kmpw4pc2xrb7dbl4",
    "Syncthing": "onboarding_app_ef14aaa8f9cb34bb5d541122268c6ec9",
    "Duplicati": "blrnitrkb1q06vhl4efrswn4",
    "n8n": "dggje28afm79zm7b3iln5p5r",
    "Unraid": "onboarding_app_886047f00b93cab6d6ddb017b88d8ea8",
    "Dockhand": "onboarding_app_d150fa1073642a7e4b5298a843a36c6b",
    "Netdata": "onboarding_app_6f2391db76faf39c349d1a43c662e027",
    "Pi-hole": "onboarding_app_636cdbde5983537bddc0a624e98d4385",
    "Crafty": "r4b870k14rl479a69bscc2tm",
}


def uid() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=24))


# ---- tile builders: (kind, options, integrationIds, desktop size, phone size) ----

def entity(entity_id, name, unit="", clickable=False, w=1):
    return ("smartHome-entityState",
            {"entityId": entity_id, "displayName": name, "entityUnit": unit, "clickable": clickable},
            [HA], (w, 1), (1, 1))


def light(entity_id, name):
    return entity(entity_id, name, clickable=True, w=2)


def app(name):
    return ("app", {"appId": APP[name], "pingEnabled": True, "openInNewTab": True, "showTitle": True},
            [], (1, 1), (1, 1))


def widget(kind, integrations, w, h, ph, options=None):
    return (kind, options or {}, integrations, (w, h), (3, ph))


# Group border colors: one saturated color per group.
ACCENT = {
    "Climate & air": "#ff8000", "Security": "#ffe000", "Lights": "#00e676",
    "Needs attention": "#ff2020", "Apps": "#ff4fc3", "Server": "#b06cff",
}

CHICAGO = {"name": "Chicago", "latitude": 41.948577, "longitude": -87.7001841}

# ---- the board: (title or None for no frame, desktop width, tiles[, fixed desktop (x, y)]) ----
# Top: clock + weather on the left, "Needs attention" on the right.
GROUPS = [
    (None, 12, [
        # Clock with the weather built in (the separate weather widget draws huge arrows in short tiles).
        widget("clock", [], 6, 1, 1, {"is24HourFormat": False, "customTimeFormat": "h:mm A",
                                      "useCustomTimezone": True, "timezone": "America/Chicago",
                                      "showDate": True, "dateFormat": "dddd, MMMM D",
                                      "showWeather": True, "weatherLocation": CHICAGO,
                                      "isWeatherFormatFahrenheit": True}),
    ]),
    ("Needs attention", 6, [
        entity("sensor.motion_detector_battery_level", "Motion battery", "%", w=2),
        entity("sensor.glass_break_battery_level", "Glass-break", "%", w=2),
        entity("sensor.litter_robot_waste_drawer", "Litter drawer", w=2),
    ], (6, 0)),
    ("Climate & air", 6, [
        entity("climate.living_room_thermostat", "Thermostat", w=2),
        entity("sensor.living_room_thermostat_humidity", "Living room humidity", "%", w=2),
        entity("sensor.office_awair_element_temperature", "Office", "°F"),
        entity("sensor.office_awair_element_humidity", "Office humidity", "%"),
        entity("sensor.office_awair_element_score", "Air score", w=2),
        entity("sensor.office_awair_element_carbon_dioxide", "CO₂", "ppm", w=2),
        entity("sensor.office_awair_element_pm2_5", "PM2.5", "µg/m³", w=2),
    ]),
    ("Security", 6, [
        entity("alarm_control_panel.waveland", "Alarm", w=2),
        entity("lock.front_door", "Front door", w=2),
        entity("lock.back_door", "Back door", w=2),
        entity("cover.bedroom_blind", "Bedroom blind", w=3),
        entity("cover.back_door_blind", "Back door blind", w=3),
    ]),
    ("Lights", 12, [
        light("light.living_room_lights", "Living room"),
        light("light.kitchen_lights", "Kitchen"),
        light("light.office_lights", "Office"),
        light("light.bedroom_lights", "Bedroom"),
        light("light.decorative_lights", "Decorative"),
        light("light.kitchen_undercounter", "Undercounter"),
    ]),
    ("Apps", 12, [app(n) for n in APP]),
    ("Server", 12, [
        widget("systemResources", [UNRAID], 4, 4, 3),
        widget("systemDisks", [UNRAID], 4, 4, 4),
        widget("healthMonitoring", [UNRAID], 4, 4, 5),
        widget("dockerContainers", [], 8, 3, 4),
        widget("dnsHoleSummary", [PIHOLE], 4, 2, 2),
        widget("dnsHoleControls", [PIHOLE], 4, 1, 1),
    ]),
]


def pack(tiles, cols, size_index):
    """First-fit, row-major. Returns [(x, y, w, h)] and the total height."""
    taken = set()
    out = []
    for t in tiles:
        w, h = t[size_index]
        w = min(w, cols)
        y = 0
        while True:
            spot = next((x for x in range(cols - w + 1)
                         if all((x + dx, y + dy) not in taken for dx in range(w) for dy in range(h))), None)
            if spot is not None:
                break
            y += 1
        for dx in range(w):
            for dy in range(h):
                taken.add((spot + dx, y + dy))
        out.append((spot, y, w, h))
    height = max((y + h for _, y, _, h in out), default=1)
    return out, height


def build(board):
    layouts = {l["role"]: l for l in board["layouts"]}
    base, mobile = layouts["base"], layouts["mobile"]
    root = board["sections"][0]["id"]
    sections = [{"id": root, "kind": "empty", "yOffset": 0, "xOffset": 0}]
    items = []
    # Groups sit side by side when two half-width ones follow each other.
    cursor = {"base": (0, 0, 0), "mobile": 0}  # base: (x, y, row height)
    for title, width, tiles, *fixed in GROUPS:
        base_pos, base_h = pack(tiles, width, 3)
        mob_pos, mob_h = pack(tiles, 3, 4)
        if title:
            # A titled section: tiles are placed inside it.
            sid = uid()
            x, y, row_h = cursor["base"]
            if fixed:
                x, y = fixed[0]
            elif x + width > 12:
                x, y, row_h = 0, y + row_h, 0
            sections.append({
                "id": sid, "kind": "dynamic",
                "options": {"title": title, "customCssClasses": [], "borderColor": ACCENT.get(title, ""), "showLabel": True,
                            "collapsible": False, "showOpenAll": False, "scrollable": False},
                "layouts": [
                    {"layoutId": base["id"], "xOffset": x, "yOffset": y, "width": width,
                     "height": base_h, "parentSectionId": root},
                    {"layoutId": mobile["id"], "xOffset": 0, "yOffset": cursor["mobile"], "width": 3,
                     "height": mob_h, "parentSectionId": root},
                ],
            })
            parent, x0, y0, my0 = sid, 0, 0, 0
            if not fixed:  # a fixed group sits in space the layout already reserved
                cursor["base"] = (x + width, y, max(row_h, base_h))
            cursor["mobile"] += mob_h
        else:
            x, y, row_h = cursor["base"]
            parent, x0, y0, my0 = root, 0, y + row_h, cursor["mobile"]
            cursor["base"] = (0, y + row_h + base_h, 0)
            cursor["mobile"] += mob_h
        for t, (bx, by, bw, bh), (mx, my, mw, mh) in zip(tiles, base_pos, mob_pos):
            kind, options, integrations = t[0], t[1], t[2]
            items.append({
                "id": uid(), "kind": kind, "options": options, "integrationIds": integrations,
                "advancedOptions": {"title": None, "customCssClasses": [], "borderColor": ""},
                "layouts": [
                    {"layoutId": base["id"], "xOffset": x0 + bx, "yOffset": y0 + by, "width": bw, "height": bh,
                     "sectionId": parent},
                    {"layoutId": mobile["id"], "xOffset": mx, "yOffset": my0 + my, "width": mw, "height": mh,
                     "sectionId": parent},
                ],
            })
    return sections, items


if __name__ == "__main__":
    c = C("homarr")
    board = json.loads(c.tool("board_getBoardByName", {"name": BOARD}))
    sections, items = build(board)
    print(f"{len(sections)} sections, {len(items)} items")
    if "--dry" in sys.argv:
        print(json.dumps(sections, indent=1)[:3000])
    else:
        print(c.tool("board_saveBoard", {"id": board["id"], "sections": sections, "items": items})[:1500])
