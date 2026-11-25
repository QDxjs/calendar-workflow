"""Create and verify the portable package's file inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from generate import APP_VERSION


INVENTORY = "_internal/PACKAGE_SHA256.json"


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def inventory(root: Path) -> dict[str, Path]:
    files = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Package contains a symbolic link: {path.relative_to(root).as_posix()}")
        relative_path = path.relative_to(root)
        if relative_path.parts[0].casefold() == "calendar_runs":
            continue
        if path != root / INVENTORY and path.is_file():
            files[relative_path.as_posix()] = path
    return files


def write_inventory(root: Path) -> None:
    files = inventory(root)
    if "CalendarWorkflow.exe" not in files:
        raise ValueError("CalendarWorkflow.exe is missing from the package.")
    payload = {"version": APP_VERSION, "sha256": {name: digest(files[name]) for name in sorted(files)}}
    with (root / INVENTORY).open("x", encoding="utf-8", newline="\n") as target:
        json.dump(payload, target, indent=2, ensure_ascii=False)
        target.write("\n")


def verify_inventory(root: Path) -> int:
    payload = json.loads((root / INVENTORY).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != APP_VERSION:
        raise ValueError("Package inventory version does not match the application.")
    expected = payload.get("sha256")
    if not isinstance(expected, dict) or "CalendarWorkflow.exe" not in expected:
        raise ValueError("Package inventory is incomplete.")
    if any(not isinstance(name, str) or not isinstance(value, str) or len(value) != 64 for name, value in expected.items()):
        raise ValueError("Package inventory contains invalid file records.")
    actual = inventory(root)
    missing = expected.keys() - actual.keys()
    extra = actual.keys() - expected.keys()
    if missing or extra:
        details = [f"missing: {', '.join(sorted(missing)[:5])}"] if missing else []
        if extra:
            details.append(f"unexpected: {', '.join(sorted(extra)[:5])}")
        raise ValueError("Package file list differs (" + "; ".join(details) + ").")
    for name in sorted(actual):
        if digest(actual[name]) != expected[name]:
            raise ValueError(f"SHA-256 mismatch: {name}")
    return len(actual)


def check_inventory(root: Path) -> int:
    try:
        count = verify_inventory(root)
    except (OSError, ValueError) as exc:
        print(f"Package verification failed: {exc}", file=sys.stderr)
        return 1
    print(f"Package SHA-256 verification passed: {count} files.", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        write_inventory(args.directory)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Could not create package inventory: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
