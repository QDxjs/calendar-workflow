"""Collect notices and installed build-dependency licenses for a portable release."""

from __future__ import annotations

import argparse
from importlib.metadata import distribution
import json
from pathlib import Path
import platform
import shutil
import sys

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


ROOT = Path(__file__).resolve().parents[1]


def collect(documentation: Path) -> None:
    documentation.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "LICENSE", documentation / "LICENSE")
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", documentation / "THIRD_PARTY_NOTICES.md")
    notices = documentation / "THIRD_PARTY_NOTICES"
    shutil.copytree(ROOT / "third_party" / "qt", notices / "qt", dirs_exist_ok=True)
    python_license = next(
        (path for path in (Path(sys.base_prefix) / "LICENSE.txt", Path(sys.base_prefix) / "LICENSE") if path.is_file()),
        None,
    )
    if python_license is None:
        raise FileNotFoundError("The build Python installation is missing its license text.")
    shutil.copy2(python_license, notices / "PYTHON-LICENSE.txt")

    pending = ["PyInstaller", "PySide6"]
    packages: dict[str, dict[str, object]] = {}
    while pending:
        name = canonicalize_name(pending.pop())
        if name in packages:
            continue
        installed = distribution(name)
        copied = []
        for relative in installed.files or []:
            if not any(word in part.lower() for part in relative.parts for word in ("license", "copying", "notice")):
                continue
            source = Path(installed.locate_file(relative))
            if not source.is_file() or ".." in relative.parts:
                continue
            target = notices / "python-packages" / name / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied.append(target.relative_to(documentation).as_posix())
        packages[name] = {
            "version": installed.version,
            "project_urls": installed.metadata.get_all("Project-URL") or [],
            "license": installed.metadata.get("License-Expression") or installed.metadata.get("License"),
            "license_files": sorted(copied),
        }
        for dependency in installed.requires or []:
            requirement = Requirement(dependency)
            if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
                pending.append(requirement.name)

    payload = {"python": platform.python_version(), "packages": dict(sorted(packages.items()))}
    (documentation / "BUILD_DEPENDENCIES.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(f"Collected Python, Qt and license records for {len(packages)} build dependencies.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("documentation", type=Path)
    collect(parser.parse_args().documentation)
