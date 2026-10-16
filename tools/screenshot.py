"""Screenshot the preview sheet (every demo at every size) with headless Edge.

Usage, with the server running on port 8080:
    python tools/screenshot.py              # all scenarios
    python tools/screenshot.py 1 4 done     # some scenarios
Writes previews/preview.png.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BASE = "http://127.0.0.1:8080"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
OUT = Path(__file__).resolve().parent.parent / "previews"
ROW_HEIGHT = 304  # tallest frame (720 x 0.4 = 288) plus spacing
WIDTH = 960
CHROME = 140  # headless Edge's viewport is shorter than --window-size
ALL_DEMOS = 10


def shoot(demos: list[str]) -> Path:
    OUT.mkdir(exist_ok=True)
    out = OUT / "preview.png"
    rows = len(demos) or ALL_DEMOS
    query = f"?demos={','.join(demos)}" if demos else ""
    subprocess.run(
        [
            str(EDGE), "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--force-device-scale-factor=1", f"--window-size={WIDTH},{rows * ROW_HEIGHT + CHROME}",
            "--virtual-time-budget=8000", f"--screenshot={out}",
            f"{BASE}/preview/{query}",
        ],
        check=True, capture_output=True, timeout=90,
    )
    return out


if __name__ == "__main__":
    print(shoot(sys.argv[1:]))
