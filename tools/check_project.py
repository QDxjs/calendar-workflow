"""Check the publishable file set and pinned resources without printing secrets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}\b"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b"),
    re.compile(r"[A-Za-z]:\\(?:Users|agentDATA)\\", re.IGNORECASE),
]
FORBIDDEN_ROOTS = {"output", "dist", "build", "calendar_runs", ".venv", "venv", "__pycache__"}


def check() -> int:
    runtime_requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    pyside_pin = re.search(r"(?m)^PySide6==([^\s#]+)\s*$", runtime_requirements)
    qt_notices = json.loads((ROOT / "third_party/qt/SOURCE.json").read_text(encoding="utf-8"))
    if pyside_pin is None or pyside_pin.group(1) != qt_notices["version"]:
        raise ValueError("PySide6 version and Qt license-source version differ; review and update the upstream notices before merging.")

    resources = json.loads((ROOT / "third_party/manifest.json").read_text(encoding="utf-8"))["files"]
    for relative, record in resources.items():
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        if actual != record["sha256"]:
            raise ValueError(f"Pinned resource changed: {relative}; review its source and update the manifest deliberately.")

    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT, check=True, capture_output=True,
    )
    files = sorted(set(name.decode("utf-8") for name in result.stdout.split(b"\0") if name))
    for relative in files:
        path = Path(relative)
        if (
            path.parts[0] in FORBIDDEN_ROOTS
            or "__pycache__" in path.parts
            or path.name == "chinese-gushiwen-sentences.json"
            or (path.name.startswith(".env") and path.name != ".env.example")
            or path.suffix.lower() in {".zip", ".pem", ".key", ".pfx", ".p12", ".pyc"}
        ):
            raise ValueError(f"Local or generated file is in the publication set: {relative}")
        if path.suffix.lower() == ".exe":
            if relative != "tools/resvg/resvg.exe":
                raise ValueError(f"Unexpected executable: {relative}")
            continue
        if path.parts[:2] == ("docs", "images") and path.suffix.lower() == ".png":
            image = (ROOT / path).read_bytes()
            if not image.startswith(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR") or len(image) < 33 or len(image) > 4 * 1024 * 1024:
                raise ValueError(f"Invalid or oversized documentation PNG: {relative}")
            width, height = struct.unpack_from(">II", image, 16)
            if not (0 < width <= 4096 and 0 < height <= 4096) or not image.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82"):
                raise ValueError(f"Invalid documentation PNG dimensions or end marker: {relative}")
            continue
        content = (ROOT / path).read_text(encoding="utf-8-sig")
        if any(pattern.search(content) for pattern in SECRET_PATTERNS):
            raise ValueError(f"Possible secret or private local path in {relative}; review locally. Matched content is hidden.")
    print(f"Publication checks passed: {len(files)} files; {len(resources)} pinned resource hashes verified.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(check())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Publication check failed: {error}", file=sys.stderr)
        raise SystemExit(1)
