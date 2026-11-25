"""Publish validated calendar batches atomically from same-volume staging."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from collections.abc import Callable, Mapping, Sequence
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile

from calendar_models import BatchCancelled, CalendarPage


@dataclass(frozen=True)
class BatchWriterDependencies:
    app_version: str
    manifest_fields: Sequence[str]
    renderers: Mapping[str, Callable[[dict[str, object]], str]]
    metadata: Callable[[object, str, str, str], dict[str, object]]
    rasterize: Callable[[Path, Path], None]
    validate_pages: Callable[[list[CalendarPage]], None]
    validate_rendering: Callable[..., None]
    render_gallery: Callable[[list[CalendarPage], int | None], str]


def write_batch(
    pages: list[CalendarPage],
    output_dir: Path,
    *,
    seed: int | None,
    on_progress: Callable[[int, int], None] | None,
    check_cancel: Callable[[], None] | None,
    dependencies: BatchWriterDependencies,
) -> int:
    if on_progress is not None:
        on_progress(0, len(pages))
    if check_cancel is not None:
        check_cancel()
    dependencies.validate_pages(pages)
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"輸出目錄已存在，為避免覆蓋已拒絕寫入：{output_dir}")
    dependencies.validate_rendering(pages, check_cancel=check_cancel)

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    lock_dir = output_dir.parent / f".{output_dir.name}.publish-lock"
    try:
        lock_dir.mkdir()
    except FileExistsError as exc:
        raise FileExistsError(f"相同批次正在生成，或发布锁尚未清理：{output_dir}") from exc
    staging_dir: Path | None = None
    terminal_progress = on_progress is None and sys.stdout is not None and sys.stdout.isatty()
    try:
        if output_dir.exists():
            raise FileExistsError(f"輸出目錄已存在，為避免覆蓋已拒絕寫入：{output_dir}")
        staging_dir = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=output_dir.parent))
        svg_dir = staging_dir / "svg"
        png_dir = staging_dir / "png"
        svg_dir.mkdir()
        png_dir.mkdir()
        manifest_path = staging_dir / "manifest.csv"
        with manifest_path.open("w", encoding="utf-8-sig", newline="") as manifest_file:
            writer = csv.DictWriter(manifest_file, fieldnames=dependencies.manifest_fields)
            writer.writeheader()
            for index, page in enumerate(pages, start=1):
                progress = f"生成进度 {index}/{len(pages)} · {page.target_date.isoformat()} · 版式 {page.layout}"
                if terminal_progress:
                    print(f"\r{progress}", end="", flush=True)
                elif on_progress is None and (index == 1 or index % 10 == 0 or index == len(pages)):
                    print(progress, flush=True)
                try:
                    day_metadata = dependencies.metadata(
                        page.target_date, page.layout, page.quote, page.source,
                    )
                    basename = f"{page.target_date.isoformat()}_layout-{page.layout}"
                    svg_path = svg_dir / f"{basename}.svg"
                    png_path = png_dir / f"{basename}.png"
                    svg_path.write_text(dependencies.renderers[page.layout](day_metadata), encoding="utf-8")
                    dependencies.rasterize(svg_path, png_path)
                    writer.writerow({
                        "date": page.target_date.isoformat(),
                        "iso_week_year": day_metadata["week_year"],
                        "iso_week": day_metadata["week"],
                        "iso_week_label": day_metadata["week_label"],
                        "layout_selection": page.layout_selection,
                        "layout": page.layout,
                        "quote": page.quote,
                        "source": page.source,
                        "quote_id": page.quote_id,
                        "seed": "" if seed is None else seed,
                        "app_version": dependencies.app_version,
                        "python_version": platform.python_version(),
                    })
                except BatchCancelled:
                    raise
                except Exception as exc:
                    raise RuntimeError(
                        f"生成 {page.target_date.isoformat()}（版式 {page.layout}）失败：{exc}"
                    ) from exc
                if on_progress is not None:
                    on_progress(index, len(pages))

        (staging_dir / "index.html").write_text(dependencies.render_gallery(pages, seed), encoding="utf-8")
        if check_cancel is not None:
            check_cancel()
        os.rename(staging_dir, output_dir)
    finally:
        if terminal_progress:
            print()
        if staging_dir is not None:
            shutil.rmtree(staging_dir, ignore_errors=True)
        shutil.rmtree(lock_dir, ignore_errors=True)
    return len(pages)
