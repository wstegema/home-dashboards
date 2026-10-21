# home-dashboards

Glance at a screen and see what's running in the house: printers, washer, dryer. Requirements: [REQUIREMENTS.md](REQUIREMENTS.md).

One container keeps one connection to Home Assistant and serves:

| URL | What |
|---|---|
| `/status/` | The dashboard. `?demo=0`…`6`, `8`, `done`, `failed` shows fake data. |
| `/status/?view=detail` | Big screens: header clock, stage, percent, finish time, printer camera + print thumbnail, camera column |
| `/status/?view=eink` | Transparent LCD: black line art on white (white = clear glass), redraws once a minute |
| `/camera/?entity=camera.x&name=X` | One camera filling the page, refreshed every 3 s (`&every=` seconds). For embedding, e.g. Homarr. |
| `/preview/` | Every demo at 320×240 and 16:9, side by side |
| `/api/status` | The data as JSON. The page and any future client (e.g. the CYD) read only this. |
| `/api/status/stream` | Same data, pushed on change (server-sent events) |
| `/healthz` | Whether HA is connected |

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
copy .env.example .env            # paste a HA token into .env
.venv\Scripts\python -m uvicorn server.web:app --port 8090
```

- Tests: `.venv\Scripts\python -m pytest`
- Screenshot of the preview sheet: `.venv\Scripts\python tools\screenshot.py` → `previews/preview.png`

## Where to change things

| To change | Edit |
|---|---|
| Colors, fonts, ring thickness | `web/shared/tokens.css` |
| Where tiles go per layout | `web/status/layouts.css` |
| How one item looks | `web/status/ring.css`, `ring.js` |
| Clock screen | `web/status/clock.css`, `clock.js` |
| Detail view / e-ink view | `web/status/detail.css` / `eink.css` |
| Which devices are watched | `server/sources.py` (`SOURCES`) |
| Cameras in the detail view's side column | `server/sources.py` (`CAMERAS`) |
| Running / done rules | `server/status.py` (with tests in `tests/`) |

The UI is plain HTML, CSS and JS modules, so there's no build step: edit a file and reload the browser.

## Deploy (Dockhand on Unraid)

1. Push to `main` on GitHub. The Action runs the tests and publishes `ghcr.io/<owner>/home-dashboards:latest`.
2. In Dockhand, create a stack from `compose.yaml` and set `HA_URL` and `HA_TOKEN` in its environment.
3. Open `http://<unraid>:8095/status/`.

The image is public, so Dockhand needs no registry login. To update, pull and redeploy the stack in Dockhand.

To edit the UI on the server without a new image, copy `web/` to the server and add a volume to the stack:
`- /mnt/user/appdata/home-dashboards/web:/app/web:ro`
