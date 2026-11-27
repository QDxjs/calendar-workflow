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
    target = preferences_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    stored, _warning = _read_settings()
    if directory is None:
        stored.pop("output_directory", None)
    else:
        stored["output_directory"] = str(directory)
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
