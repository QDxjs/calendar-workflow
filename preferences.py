"""Minimal, atomic per-user preferences for the calendar application."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile


def preferences_path() -> Path:
    local_data = Path(os.environ.get("LOCALAPPDATA", ""))
    if not local_data.is_absolute():
        local_data = Path.home() / "AppData" / "Local"
    return local_data / "CalendarWorkflow" / "settings.json"


def load_output_directory(default: Path) -> Path:
    try:
        stored = json.loads(preferences_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
    if not isinstance(stored, dict):
        return default
    path = stored.get("output_directory")
    if not isinstance(path, str) or not path.strip() or "\0" in path:
        return default
    candidate = Path(path)
    return candidate if candidate.is_absolute() else default


def save_output_directory(directory: Path) -> None:
    if not directory.is_absolute():
        raise ValueError("输出目录必须是绝对路径。")
    target = preferences_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    contents = json.dumps({"output_directory": str(directory)}, ensure_ascii=False, indent=2) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", delete=False,
            dir=target.parent, prefix=".settings-", suffix=".tmp",
        ) as settings:
            temporary = Path(settings.name)
            settings.write(contents)
            settings.flush()
            os.fsync(settings.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
