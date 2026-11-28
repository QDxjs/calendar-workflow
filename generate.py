#!/usr/bin/env python3
"""Render editable daily literature calendar pages as standalone SVG files."""

from __future__ import annotations

from collections.abc import Callable
import subprocess
import sys
from pathlib import Path

from gallery import render_gallery
from calendar_models import BatchCancelled, CalendarPage, WEEKDAYS
from batch_publisher import BatchWriterDependencies, write_batch as _write_batch
from calendar_layout_a import render_a
from calendar_layout_b import render_b as _render_b
from calendar_layout_c import render_c
from calendar_layout_d import render_d
from calendar_layout_e import render_e
from calendar_layout_f import render_f
from calendar_layout_g import render_g
from calendar_layout_h import render_h
from calendar_layout_i import render_i
from calendar_imports import (
    ReplayDetails, prepare_pages as _prepare_pages, prepare_replay as _prepare_replay,
    prepare_replay_with_details as _prepare_replay_with_details,
)
from csv_inputs import parse_csv_date, read_rows
from page_validation import validate_pages as _validate_pages
from png_renderer import (
    PNG_SCALE, RENDER_TIMEOUT_SECONDS,
    svg_to_png as _svg_to_png, validate_png as _validate_png,
)
from svg_primitives import (
    H, W, balance_quote_lines, common_defs, esc, label_block, line, metadata,
    quote_block, rect, svg_open, text, text_width_units, wrap_text,
)
from svg_validation import validate_rendering as _validate_rendering

APP_VERSION = "0.6.8"
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
APP_ROOT = (Path(sys.executable).resolve().parent if getattr(sys, "frozen", False)
            else Path(__file__).resolve().parent)
RESVG = RESOURCE_ROOT / "tools" / "resvg" / "resvg.exe"
PNG_SCALE = 1
RENDER_TIMEOUT_SECONDS = 120


def svg_to_png(svg_path: Path, png_path: Path, *, scale: int = PNG_SCALE) -> None:
    """Compatibility entry point for rasterizing one calendar SVG."""
    _svg_to_png(
        svg_path, png_path, renderer_path=RESVG, width=W, height=H,
        scale=scale, timeout_seconds=RENDER_TIMEOUT_SECONDS,
    )


def validate_png(png_path: Path, *, scale: int = PNG_SCALE) -> None:
    """Compatibility entry point for validating a rendered calendar PNG."""
    _validate_png(png_path, width=W, height=H, scale=scale)


render_b = _render_b


RENDERERS = {
    "A": render_a, "B": render_b, "C": render_c, "D": render_d, "E": render_e,
    "F": render_f, "G": render_g, "H": render_h, "I": render_i,
}
LAYOUT_LABELS = {
    "A": "网格", "B": "几何分栏", "C": "留白", "D": "双色圆形",
    "E": "框式语录", "F": "均衡网格", "G": "几何分栏变体",
    "H": "中央大日号", "I": "双色圆形变体",
}

MANIFEST_FIELDS = [
    "date", "iso_week_year", "iso_week", "iso_week_label",
    "layout_selection", "layout", "quote", "source", "quote_id", "creator", "variant", "seed",
    "app_version", "python_version",
]
def validate_pages(pages: list[CalendarPage]) -> None:
    _validate_pages(pages, renderers=RENDERERS)


def write_batch(
    pages: list[CalendarPage],
    output_dir: Path,
    *,
    seed: int | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    check_cancel: Callable[[], None] | None = None,
) -> int:
    """Render validated calendar pages into a batch, publishing only on success."""
    dependencies = BatchWriterDependencies(
        app_version=APP_VERSION,
        manifest_fields=MANIFEST_FIELDS,
        renderers=RENDERERS,
        metadata=metadata,
        rasterize=svg_to_png,
        validate_pages=validate_pages,
        validate_rendering=validate_rendering,
        render_gallery=render_gallery,
    )
    return _write_batch(
        pages,
        output_dir,
        seed=seed,
        on_progress=on_progress,
        check_cancel=check_cancel,
        dependencies=dependencies,
    )

def prepare_pages(
    input_path: Path, *, seed: int | None = None, creator: str = "",
) -> list[CalendarPage]:
    return _prepare_pages(
        input_path, seed=seed, creator=creator,
        renderers=RENDERERS, validate=validate_pages,
    )


def prepare_replay(manifest_path: Path) -> tuple[list[CalendarPage], int | None]:
    """Recover recorded content and layouts through the stable generator interface."""
    return _prepare_replay(manifest_path, renderers=RENDERERS, validate=validate_pages)


def prepare_replay_with_details(manifest_path: Path) -> ReplayDetails:
    return _prepare_replay_with_details(manifest_path, renderers=RENDERERS, validate=validate_pages)


def validate_rendering(
    pages: list[CalendarPage],
    *,
    exhaustive_random_layouts: bool = False,
    check_cancel: Callable[[], None] | None = None,
) -> None:
    _validate_rendering(
        pages,
        renderers=RENDERERS,
        metadata=metadata,
        validate_pages=validate_pages,
        exhaustive_random_layouts=exhaustive_random_layouts,
        check_cancel=check_cancel,
    )


def generate(input_path: Path, output_dir: Path, *, seed: int | None = None) -> int:
    pages = prepare_pages(input_path, seed=seed)
    return publish_with_summary(pages, output_dir, seed=seed)


def publish_with_summary(pages: list[CalendarPage], output_dir: Path, *, seed: int | None) -> int:
    count = write_batch(pages, output_dir, seed=seed)
    print(f"批次目录：{output_dir}")
    print(f"批次预览：{output_dir / 'index.html'}")
    print(f"生成记录：{output_dir / 'manifest.csv'}")
    return count


def main() -> int:
    from calendar_cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
