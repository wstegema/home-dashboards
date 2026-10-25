# Homarr `home` board

Launcher and home overview at http://192.168.1.201:10004 (home board on desktop and phone).
Part of the home-dashboards project, but the board never shows or links to the status app (no embed, app tile, camera or icon from it).

| Group | What |
|---|---|
| (top) | Clock with weather (Chicago); Needs attention: low batteries, litter drawer |
| Climate & air | Thermostat, humidity, office temp, Awair score / CO₂ / PM2.5 |
| Security | Alarm, door locks, blinds |
| Lights | Room lights; tap to toggle |
| Apps | Every Unraid service with a web UI |
| Server | CPU/RAM, disks, health, Docker, Pi-hole |

- **Change the board:** edit `GROUPS` in `build_home_board.py`, then `python -I homarr/build_home_board.py`. It replaces the whole board, so edits made by hand in Homarr are lost.
- **Talks to Homarr** through `../../unraid-management/tools/mcpc.py`, which holds the API key.
- **See it like a user:** `.venv/bin/python homarr/screenshot.py home 1920x1080 390x844` logs in as the view-only `claude-viewer` user (credentials in `../../unraid-management/.homarr-viewer.env`) and saves full-page shots to `previews/`. That user can't read Docker or Pi-hole, so those widgets show "Not enough permissions" in its shots only.
- **Desktop layout comes first;** the phone layout only needs to stay usable.
