"""Settings from the environment. A local .env file is read for dev runs;
in the container, Dockhand passes the same variables directly."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


_load_env_file(ROOT / ".env")

HA_URL = os.environ.get("HA_URL", "http://homeassistant.local:8123").rstrip("/")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
WEB_DIR = Path(os.environ.get("WEB_DIR", ROOT / "web"))
