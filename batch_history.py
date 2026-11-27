"""Read-only discovery of existing batches; no widgets, rendering or index files."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import queue
import threading

from calendar_models import BatchCancelled, CalendarPage
from generate import prepare_replay_with_details


@dataclass(frozen=True)
class BatchSummary:
    directory: Path
    pages: tuple[CalendarPage, ...] = ()
    seed: int | None = None
    versions: tuple[str, ...] = ()
    missing_png: int = 0
    missing_svg: int = 0
    has_preview: bool = False
    error: str = ""
    manifest_updated: str = "未知"

    @property
    def status(self) -> str:
        if self.error:
            return f"清单不可用：{self.error}"
        issues = []
        if not self.has_preview:
            issues.append("缺少网页")
        if self.missing_png:
            issues.append(f"缺 {self.missing_png} 张 PNG")
        if self.missing_svg:
            issues.append(f"缺 {self.missing_svg} 张 SVG")
        return "；".join(issues) or "文件齐全"

    @property
    def date_range(self) -> str:
        if not self.pages:
            return "—"
        days = [page.target_date for page in self.pages]
        first, last = min(days).isoformat(), max(days).isoformat()
        return first if first == last else f"{first} ～ {last}"


def inspect_batch(directory: Path, check_cancel: Callable[[], None] = lambda: None) -> BatchSummary:
    check_cancel()
    manifest = directory / "manifest.csv"
    try:
        updated = datetime.fromtimestamp(manifest.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    except (OSError, ValueError, OverflowError):
        updated = "未知"
    try:
        details = prepare_replay_with_details(manifest)
        pages, seed, versions = details.pages, details.seed, details.versions
        missing_png = missing_svg = 0
        for page in pages:
            check_cancel()
            basename = f"{page.target_date.isoformat()}_layout-{page.layout}"
            missing_png += not (directory / "png" / f"{basename}.png").is_file()
            missing_svg += not (directory / "svg" / f"{basename}.svg").is_file()
        check_cancel()
        return BatchSummary(directory, tuple(pages), seed, versions, missing_png,
                            missing_svg, (directory / "index.html").is_file(), manifest_updated=updated)
    except (OSError, ValueError) as exc:
        return BatchSummary(directory, error=str(exc), manifest_updated=updated)


def scan_history(root: Path, check_cancel: Callable[[], None] = lambda: None) -> Iterator[BatchSummary]:
    """Inspect only this batch or immediate children within the selected root."""
    check_cancel()
    # Keep the caller's absolute spelling in returned summaries.  Windows can
    # present the same temporary directory through an 8.3 alias; resolving the
    # root for display would then make otherwise equal Path values compare
    # differently.  Use the resolved form only for the containment check.
    root = root.absolute()
    resolved_root = root.resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError("历史位置不是文件夹。")
    if (root / "manifest.csv").is_file():
        yield inspect_batch(root, check_cancel)
        return
    for child in sorted(root.iterdir(), key=lambda path: path.name.casefold(), reverse=True):
        check_cancel()
        if child.name.startswith(".") or child.name.endswith(".publish-lock"):
            continue
        try:
            if not child.resolve().is_relative_to(resolved_root) or not child.is_dir():
                continue
            if (child / "manifest.csv").is_file():
                yield inspect_batch(child, check_cancel)
        except (OSError, RuntimeError) as exc:
            yield BatchSummary(child, error=str(exc))


def run_history_scan(root: Path, cancel: threading.Event, events: queue.Queue) -> None:
    def check_cancel() -> None:
        if cancel.is_set():
            raise BatchCancelled()

    try:
        for summary in scan_history(root, check_cancel):
            check_cancel()
            events.put(("batch", summary))
        check_cancel()
        events.put(("done", None))
    except BatchCancelled:
        events.put(("cancelled", None))
    except (OSError, ValueError, RuntimeError) as exc:
        events.put(("error", str(exc)))
