"""Screenshot a Homarr board while logged in as the view-only user.

Credentials come from ../unraid-management/.homarr-viewer.env (never committed).
    python screenshot.py [board] [width]x[height] ...
    python screenshot.py home 1920x1080 390x844
Writes previews/homarr-<board>-<w>x<h>.png (full page).
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ENV = Path(__file__).resolve().parents[2] / "unraid-management" / ".homarr-viewer.env"
OUT = Path(__file__).resolve().parents[1] / "previews"


def creds() -> dict:
    pairs = (line.split("=", 1) for line in ENV.read_text().splitlines() if "=" in line and not line.startswith("#"))
    return {k.strip(): v.strip() for k, v in pairs}


def main(board: str, sizes: list[str]) -> None:
    c = creds()
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, color_scheme="dark")
        page = ctx.new_page()
        page.goto(f"{c['HOMARR_URL']}/auth/login")
        page.locator("input[autocomplete='username']").first.fill(c["HOMARR_USER"])
        page.locator("input[type='password']").first.fill(c["HOMARR_PASSWORD"])
        page.locator("button[type='submit']").first.click()
        page.wait_for_url(lambda url: "/auth/login" not in url, timeout=15000)
        for size in sizes:
            w, h = (int(n) for n in size.split("x"))
            page.set_viewport_size({"width": w, "height": h})
            page.goto(f"{c['HOMARR_URL']}/boards/{board}")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(4000)  # widgets fetch their data after load
            skip = page.get_by_text("Skip tour")
            if skip.count():  # first-visit onboarding popup
                skip.first.click()
                page.wait_for_timeout(500)
            out = OUT / f"homarr-{board}-{w}x{h}.png"
            page.screenshot(path=str(out), full_page=True)
            print(out, page.url)
        browser.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    main(args[0] if args else "home", args[1:] or ["1920x1080", "390x844"])
