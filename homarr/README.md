# Homarr `home` board

The launcher and home overview at http://192.168.1.201:10004 (set as home on desktop and phone).

| Group | What |
|---|---|
| (top) | Clock, weather (Chicago), home-status dashboard |
| Climate & air | Thermostat, temps, humidity, Awair score / CO₂ / PM2.5 |
| Security | Alarm, door locks, blinds |
| Lights | Room lights; tap to toggle |
| Needs attention | Low sensor batteries, litter drawer |
| Apps | Every Unraid service with a web UI |
| Server | CPU/RAM, disks, health, Docker, Pi-hole |

- **Change the board:** edit `GROUPS` in `build_home_board.py`, then `python -I homarr/build_home_board.py`. It replaces the whole board, so changes made by hand in Homarr are lost.
- **Look:** group border colors come from the dashboard palette (`web/shared/tokens.css`). Board CSS and colors are set in Homarr → board settings.
- **See it like a user:** `python tools/homarr_shot.py home 1920x1080 390x844` logs in as the view-only `claude-viewer` user (credentials in `../unraid-management/.homarr-viewer.env`) and saves full-page screenshots to `previews/`. That user can't read Docker or Pi-hole, so those widgets show "Not enough permissions" in its screenshots only.
