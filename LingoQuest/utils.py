from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any


APP_NAME = "LingoQuest"


def app_storage_dir() -> Path:
    if getattr(sys, "frozen", False):
        base_dir = Path(os.getenv("APPDATA") or (Path.home() / "AppData" / "Roaming")) / APP_NAME
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir
    return Path(__file__).resolve().parent


def resolve_app_file(filename: str) -> Path:
    return app_storage_dir() / filename


def load_json_state(pathlike: str | Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    path = Path(pathlike)
    if not path.exists():
        return dict(default or {})

    try:
        loaded = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return dict(default or {})

    if isinstance(loaded, dict):
        return loaded
    return dict(default or {})


def save_json_state(pathlike: str | Path, payload: dict[str, Any]) -> None:
    path = Path(pathlike)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def today_key(day: date | None = None) -> str:
    return (day or date.today()).isoformat()
