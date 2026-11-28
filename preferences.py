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


def _read_settings() -> tuple[dict, str]:
    try:
        stored = json.loads(preferences_path().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, ""
    except (OSError, ValueError) as exc:
        return {}, f"无法读取偏好设置，已使用默认目录；可重新选择保存位置。详情：{exc}"
    if not isinstance(stored, dict):
        return {}, "偏好设置格式无效，已使用默认目录；可重新选择保存位置。"
    return stored, ""


def preferences_warning() -> str:
    stored, warning = _read_settings()
    if warning or "output_directory" not in stored:
        return warning
    path = stored["output_directory"]
    if not isinstance(path, str) or not path.strip() or "\0" in path or not Path(path).is_absolute():
        return "保存位置设置无效，已使用默认目录；可重新选择保存位置。"
    return ""


def load_output_directory(default: Path) -> Path:
    stored, _warning = _read_settings()
    path = stored.get("output_directory")
    if not isinstance(path, str) or not path.strip() or "\0" in path:
        return default
    candidate = Path(path)
    return candidate if candidate.is_absolute() else default


def save_output_directory(directory: Path | None) -> None:
    """Persist an explicit directory, or clear it to follow the running app."""
    if directory is not None and not directory.is_absolute():
        raise ValueError("输出目录必须是绝对路径。")
    stored, _warning = _read_settings()
    if directory is None:
        stored.pop("output_directory", None)
    else:
        stored["output_directory"] = str(directory)
    _write_settings(stored)


def load_creator_preferences() -> tuple[bool, str]:
    """Return (enabled, creator_text), defaulting to (False, '')."""
    stored, _warning = _read_settings()
    raw_enabled = stored.get("creator_enabled")
    enabled = raw_enabled if isinstance(raw_enabled, bool) else False
    raw_text = stored.get("creator_text")
    creator_text = raw_text if isinstance(raw_text, str) else ""
    return enabled, creator_text


def save_creator_preferences(enabled: bool, creator_text: str) -> None:
    """Persist creator checkbox state and default creator text atomically."""
    stored, _warning = _read_settings()
    stored["creator_enabled"] = bool(enabled)
    stored["creator_text"] = creator_text
    _write_settings(stored)


def _write_settings(stored: dict) -> None:
    target = preferences_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    contents = json.dumps(stored, ensure_ascii=False, indent=2) + "\n"
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
