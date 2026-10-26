"""Screenshot the CYD screen without the CYD.

Builds cyd-home-status.yaml for ESPHome's Linux "host" platform with an SDL window
in place of the CYD's hardware, runs it on a virtual screen (Xvfb) and saves
previews/cyd-<scenario>.png for each demo scenario.

    python tools/cyd_preview.py              # every demo scenario
    python tools/cyd_preview.py 2 done live  # some scenarios; "live" = real status

Needs: esphome (same version as the stack), libsdl2-dev, xvfb, imagemagick.
"""

import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "cyd-home-status.yaml"
BUILD = ROOT / ".cyd-host"  # gitignored
OUT = ROOT / "previews"
SCENARIOS = ["1", "2", "3", "4", "5", "6", "8", "done", "failed", "cooling", "waiting"]
DISPLAY_NUM = ":99"
SETTLE_SECONDS = 12  # first fetch at 5 s, then thumbnails

# CYD hardware that has no meaning on Linux.
DROP = {"esp32", "api", "ota", "wifi", "captive_portal", "spi", "output", "light",
        "touchscreen", "debug", "sensor"}

REPLACE = {
    "time": "time:\n  - platform: host\n    id: ha_time\n",
    "display": (
        "display:\n  - platform: sdl\n    id: my_display\n    update_interval: never\n"
        "    auto_clear_enabled: false\n    dimensions:\n      width: 320\n      height: 240\n"
    ),
}


def blocks(text):
    """Split YAML text into (top-level key, block text) pairs; comments stay with the next key."""
    out, key, lines = [], None, []
    for line in text.splitlines(keepends=True):
        m = re.match(r"^([a-z0-9_]+):", line)
        if m:
            out.append((key, "".join(lines)))
            key, lines = m.group(1), []
        lines.append(line)
    out.append((key, "".join(lines)))
    return out


def host_yaml(scenario):
    parts = []
    for key, text in blocks(SOURCE.read_text()):
        if key in DROP:
            continue
        if key in REPLACE:
            text = REPLACE[key]
        elif key == "lvgl":
            # No touch, and LVGL's rotation would turn the SDL window upside down.
            text = re.sub(r"^  touchscreens:\n(    .*\n)+", "", text, flags=re.M)
            text = re.sub(r"^  rotation: .*\n", "", text, flags=re.M)
        elif key == "switch" and scenario != "live":
            text = text.replace("restore_mode: ALWAYS_OFF", "restore_mode: ALWAYS_ON", 1)
        elif key == "select" and scenario != "live":
            text = re.sub(r'initial_option: ".*?"', f'initial_option: "{scenario}"', text)
            text = text.replace("restore_value: true", "restore_value: false")
        parts.append(text)
    return "host:\n\n" + "".join(parts)


def run(cmd, **kw):
    print("+", " ".join(map(str, cmd)), flush=True)
    return subprocess.run(cmd, check=True, **kw)


def main(scenarios):
    BUILD.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    xvfb = subprocess.Popen(["Xvfb", DISPLAY_NUM, "-screen", "0", "320x240x24"],
                            stderr=subprocess.DEVNULL)
    env = {**os.environ, "DISPLAY": DISPLAY_NUM}
    try:
        for scenario in scenarios:
            config = BUILD / "cyd-host.yaml"
            config.write_text(host_yaml(scenario))
            run(["esphome", "compile", config], stdout=subprocess.DEVNULL)
            program = BUILD / ".esphome/build/cyd-home-status/.pioenvs/cyd-home-status/program"
            device = subprocess.Popen([program], env=env, stdout=subprocess.DEVNULL)
            try:
                time.sleep(SETTLE_SECONDS)
                png = OUT / f"cyd-{scenario}.png"
                run(["import", "-display", DISPLAY_NUM, "-window", "root", png], env=env)
                print("saved", png.relative_to(ROOT))
            finally:
                device.terminate()
                device.wait()
    finally:
        xvfb.terminate()


if __name__ == "__main__":
    main(sys.argv[1:] or SCENARIOS)
