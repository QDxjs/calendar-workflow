"""Prepare calendar pages from CSV inputs or recorded batch manifests."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
import random
import re

from calendar_models import CalendarPage
from csv_inputs import parse_csv_date, read_rows


def prepare_pages(
    input_path: Path,
    *,
    seed: int | None = None,
    renderers: Mapping[str, object],
    validate: Callable[[list[CalendarPage]], None],
) -> list[CalendarPage]:
    rows = read_rows(input_path)
    rng = random.Random(seed)
    previous_layout: str | None = None
    pages: list[CalendarPage] = []

    for index, row in enumerate(rows):
        target_date = parse_csv_date(row["date"].strip(), index + 2)
        quote = (row.get("quote") or "").strip()
        if not quote:
            raise ValueError(f"第 {index + 2} 行缺少 quote 语录正文。")
        requested = (row.get("layout") or "").strip().upper()
        if requested in ("", "AUTO", "R", "RANDOM", "随机"):
            candidates = [layout for layout in renderers if layout != previous_layout]
            selected = rng.choice(candidates or list(renderers))
            selection_label = "random"
        else:
            selected = requested
            selection_label = requested
        if selected not in renderers:
            raise ValueError(f"第 {index + 2} 行版式应为 A–I、R 或 auto，收到：{requested!r}")

        source = (row.get("source") or "").strip()
        pages.append(CalendarPage(target_date, selection_label, selected, quote, source))
        previous_layout = selected

    validate(pages)
    return pages


def prepare_replay(
    manifest_path: Path,
    *,
    renderers: Mapping[str, object],
    validate: Callable[[list[CalendarPage]], None],
) -> tuple[list[CalendarPage], int | None]:
    """Recover recorded content and actual layouts without consulting the quote library."""
    rows = read_rows(manifest_path, extra_required=("quote_id",))
    pages: list[CalendarPage] = []
    seed: int | None = None
    for record_number, row in enumerate(rows, start=2):
        target_date = parse_csv_date(row["date"].strip(), record_number)
        iso_year, iso_week, _ = target_date.isocalendar()
        expected_iso = {
            "iso_week_year": str(iso_year),
            "iso_week": str(iso_week),
            "iso_week_label": f"{iso_year}-W{iso_week:02d}",
        }
        for field, expected in expected_iso.items():
            recorded = row.get(field, "").strip()
            if recorded and recorded != expected:
                raise ValueError(
                    f"清单第 {record_number} 条记录的 {field} 与日期 {target_date.isoformat()} 不一致。"
                )
        layout = row["layout"].strip().upper()
        if layout not in renderers:
            raise ValueError(f"清单第 {record_number} 条记录须填写实际版式 A–I，收到：{layout!r}。")
        selection = row.get("layout_selection", layout).strip()
        if selection != "random" and selection != layout:
            raise ValueError(f"清单第 {record_number} 条记录的版式选择与实际版式不一致。")
        raw_seed = row.get("seed", "").strip()
        try:
            if raw_seed and not re.fullmatch(r"-?[0-9]+", raw_seed):
                raise ValueError
            recorded_seed = int(raw_seed) if raw_seed else None
        except ValueError as exc:
            raise ValueError(f"清单第 {record_number} 条记录的随机种子必须为整数或留空。") from exc
        if record_number == 2:
            seed = recorded_seed
        elif recorded_seed != seed:
            raise ValueError(f"清单第 {record_number} 条记录的随机种子与首条记录不一致。")
        pages.append(CalendarPage(target_date, selection, layout, row["quote"], row["source"], row["quote_id"]))

    validate(pages)
    return pages, seed
