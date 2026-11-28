#!/usr/bin/env python3
"""Interactive, offline literature calendar generator."""

from __future__ import annotations

import random
import re
import os
import sys
from datetime import date, datetime
from pathlib import Path

from generate import APP_VERSION, CalendarPage, LAYOUT_LABELS, RENDERERS, write_batch
from layout_selection import resolve_layouts
from periods import dates_between, dates_in_iso_week, dates_in_month, dates_in_year
from quote_library import builtin_quotes, load_quotes


def default_output_root(*, packaged: bool) -> Path:
    if not packaged:
        return Path(__file__).resolve().parent / "output" / "calendar_runs"

    return Path(sys.executable).resolve().parent / "calendar_runs"


OUTPUT_ROOT = default_output_root(packaged=getattr(sys, "frozen", False))


def choose_period() -> str:
    """Ask for a clear calendar range choice; 0 exits without an error."""
    while True:
        print("\n选择生成范围：")
        print("  1. 单日")
        print("  2. 日期范围（开始日到结束日，包含首尾）")
        print("  3. 一周（输入该周任意一天，自动按周一至周日生成）")
        print("  4. 月份")
        print("  5. 年份")
        print("  0. 退出")
        choice = input("请输入选项：").strip()
        if choice in {"0", "1", "2", "3", "4", "5"}:
            return choice
        print("选项无效，请输入 0–5 中的数字。")


def ask_date(prompt: str) -> date:
    """Keep asking until the user enters a valid YYYYMMDD date."""
    while True:
        value = input(prompt).strip()
        if not re.fullmatch(r"\d{8}", value):
            print("请用 8 位数字 YYYYMMDD，例如 20270101。")
            continue
        try:
            return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
        except ValueError:
            print("这个日期不存在，请重新输入，例如 20270101。")


def dates_for_choice(
    choice: str, max_days: int | None = None,
) -> tuple[list[date], str, str]:
    """Return dates, a naming key, and a human-readable period label."""
    if choice == "1":
        target = ask_date("请输入目标日期（YYYYMMDD）：")
        return [target], f"date_{target:%Y%m%d}", target.isoformat()

    if choice == "2":
        start = ask_date("请输入开始日期（YYYYMMDD）：")
        while True:
            end = ask_date("请输入结束日期（YYYYMMDD）：")
            if end < start:
                print(f"结束日期不能早于开始日期 {start:%Y%m%d}，请重新输入。")
                continue
            span = (end - start).days
            if max_days is not None and span + 1 > max_days:
                print(
                    f"这段日期共 {span + 1} 天，超过当前语录库可支持的 {max_days} 天。"
                    "请缩短日期范围后重输结束日期。"
                )
                continue
            break
        selected_dates = dates_between(start, end)
        key = f"range_{start:%Y%m%d}-{end:%Y%m%d}"
        label = f"{start.isoformat()} 至 {end.isoformat()}（含首尾）"
        return selected_dates, key, label

    if choice == "3":
        while True:
            target = ask_date("请输入这一周中的任意一天（YYYYMMDD）：")
            try:
                selected_dates = dates_in_iso_week(target)
            except ValueError as exc:
                print(exc)
                continue
            break
        iso_year, iso_week, _ = target.isocalendar()
        monday = selected_dates[0]
        sunday = selected_dates[-1]
        key = f"week_{iso_year}-W{iso_week:02d}"
        label = (f"ISO {iso_year}-W{iso_week:02d}"
                 f"（{monday.isoformat()} 至 {sunday.isoformat()}）")
        return selected_dates, key, label

    if choice == "4":
        while True:
            value = input("请输入目标月份（YYYYMM 或 YYYY-MM）：").strip()
            if re.fullmatch(r"\d{6}", value):
                year, month = int(value[:4]), int(value[4:])
            elif re.fullmatch(r"\d{4}-\d{2}", value):
                year, month = int(value[:4]), int(value[5:])
            else:
                print("月份格式不正确，请输入 YYYYMM 或 YYYY-MM，例如 202701。")
                continue
            try:
                selected_dates = dates_in_month(year, month)
            except ValueError:
                print("这个年月不存在，请重新输入，例如 202701。")
                continue
            return selected_dates, f"month_{year}{month:02d}", f"{year}-{month:02d}"

    if choice == "5":
        while True:
            value = input("请输入目标年份（YYYY）：").strip()
            if not re.fullmatch(r"\d{4}", value):
                print("年份请使用 4 位数字，例如 2027。")
                continue
            year = int(value)
            try:
                selected_dates = dates_in_year(year)
            except ValueError:
                print("这个年份不存在，请重新输入 4 位数字年份。")
                continue
            return selected_dates, f"year_{year}", str(year)

    raise ValueError("无法识别的日期范围选项。")


def choose_layout() -> str:
    """Return RANDOM or an explicitly selected layout letter."""
    number_to_letter = {str(index): letter for index, letter in enumerate(LAYOUT_LABELS, start=1)}
    while True:
        print("\n选择版式：")
        print("  R. 随机（每页独立抽选，连续日期尽量不重复；直接回车也随机）")
        for index, (letter, label) in enumerate(LAYOUT_LABELS.items(), start=1):
            print(f"  {letter} / {index}. {label}")
        value = input("请输入 R、版式字母 A–I 或编号 1–9：").strip().upper()
        if value in {"", "R", "RANDOM", "AUTO", "0", "随机"}:
            return "RANDOM"
        if value in number_to_letter:
            return number_to_letter[value]
        if value in RENDERERS:
            return value
        print("版式选项无效，请输入 R、A–I 或 1–9。")


def choose_seed() -> int | None:
    while True:
        value = input("请输入可选随机种子（直接回车使用随机值）：").strip()
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            print("随机种子必须是整数，或直接回车跳过。")


def unique_output_dir(period_key: str, layout_selection: str | None, *, root: Path | None = None) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    layout_key = "random" if layout_selection == "RANDOM" else layout_selection
    layout_suffix = f"_layout-{layout_key}" if layout_key is not None else ""
    base = (OUTPUT_ROOT if root is None else root) / f"{period_key}{layout_suffix}_{stamp}"
    candidate = base
    suffix = 2
    while candidate.exists():
        candidate = Path(f"{base}_{suffix}")
        suffix += 1
    return candidate


def plan_pages(
    dates: list[date], quotes: list[dict[str, str]],
    layout_selection: str, seed: int | None = None,
    *, creator: str = "", pages_per_date: int | None = None,
    selected_quote: dict[str, str] | None = None,
) -> list[CalendarPage]:
    explicit_layouts = resolve_layouts(layout_selection, RENDERERS)
    if pages_per_date is not None and (type(pages_per_date) is not int or pages_per_date < 1):
        raise ValueError("数量必须是正整数（张 / per Date）。")
    if selected_quote is not None and (len(dates) != 1 or pages_per_date is not None):
        raise ValueError("选定语录仅支持单日的同语录换版式模式。")
    needed = len(dates) * (pages_per_date or 1)
    if selected_quote is None and len(quotes) < needed:
        raise ValueError(f"可用的不重复语录只有 {len(quotes)} 条，少于本次需要的 {needed} 条。")

    rng = random.Random(seed)
    selected_quotes = [selected_quote] if selected_quote is not None else rng.sample(quotes, k=needed)
    clean_creator = creator.strip()
    if pages_per_date is not None:
        pool = explicit_layouts or tuple(RENDERERS)
        pages: list[CalendarPage] = []
        previous_layout = None
        for index, quote in enumerate(selected_quotes):
            candidates = [layout for layout in pool if layout != previous_layout]
            previous_layout = rng.choice(candidates or list(pool))
            pages.append(CalendarPage(
                dates[index // pages_per_date], "random", previous_layout,
                quote["quote"], quote["source"], quote["quote_id"], clean_creator,
                index % pages_per_date + 1 if pages_per_date > 1 else 0,
            ))
        return pages
    if explicit_layouts:
        return [
            CalendarPage(
                target_date, layout, layout, quote["quote"], quote["source"],
                quote["quote_id"], clean_creator,
            )
            for target_date, quote in zip(dates, selected_quotes)
            for layout in explicit_layouts
        ]
    layouts: list[str] = []
    previous_layout: str | None = None
    for _ in dates:
        candidates = [layout for layout in RENDERERS if layout != previous_layout]
        previous_layout = rng.choice(candidates or list(RENDERERS))
        layouts.append(previous_layout)
    return [
        CalendarPage(
            target_date, "random", layout, quote["quote"], quote["source"],
            quote["quote_id"], clean_creator,
        )
        for target_date, quote, layout in zip(dates, selected_quotes, layouts)
    ]


def generate_period(
    dates: list[date], period_key: str, quotes: list[dict[str, str]],
    layout_selection: str, seed: int | None = None,
) -> Path:
    pages = plan_pages(dates, quotes, layout_selection, seed)
    output_dir = unique_output_dir(period_key, layout_selection)
    write_batch(pages, output_dir, seed=seed)

    print(f"已生成 SVG：{output_dir / 'svg'}")
    print(f"已生成同尺寸 PNG（1122 × 1402）：{output_dir / 'png'}")
    print(f"批次目录：{output_dir}")
    print(f"浏览器预览：{output_dir / 'index.html'}")
    print(f"语录和版式记录：{output_dir / 'manifest.csv'}")
    return output_dir


def main(quote_file: Path | None = None) -> int:
    print(f"每日文学日历生成器 v{APP_VERSION}")
    print(f"语录来源：{quote_file if quote_file else '一言句子库'}")
    try:
        quotes: list[dict[str, str]] | None = None
        while True:
            choice = choose_period()
            if choice == "0":
                print("已退出。")
                return 0
            if quotes is None:
                print("正在检查本地语录库……")
                quotes = load_quotes(quote_file) if quote_file else builtin_quotes()
            dates, folder_label, period_label = dates_for_choice(choice, max_days=len(quotes))
            if len(dates) > len(quotes):
                print(
                    f"所选范围有 {len(dates)} 天，可用的不重复语录只有 {len(quotes)} 条。"
                    "请改选较短的范围。"
                )
                continue
            break

        layout_selection = choose_layout()
        seed = choose_seed()
        layout_label = "随机版式" if layout_selection == "RANDOM" else f"指定版式 {layout_selection}"
        seed_label = "未固定" if seed is None else str(seed)
        print(f"目标范围：{period_label}；共 {len(dates)} 天；{layout_label}；随机种子 {seed_label}；可用语录 {len(quotes)} 条。")
        generate_period(dates, folder_label, quotes, layout_selection, seed)
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"无法生成：{exc}")
        return 1
    except (EOFError, KeyboardInterrupt):
        print("\n已取消。")
        return 1


if __name__ == "__main__":
    args = sys.argv[1:]
    if getattr(sys, "frozen", False):
        for stream_name in ("stdout", "stderr"):
            if getattr(sys, stream_name) is None:
                setattr(sys, stream_name, open(os.devnull, "w", encoding="utf-8"))
    if args == ["--verify-package"] or (getattr(sys, "frozen", False) and args in (["--verify-portable"], ["--verify-portable", "--full-year"])):
        from package_integrity import check_inventory

        status = check_inventory(Path(sys.executable).resolve().parent)
        if status or args == ["--verify-package"]:
            raise SystemExit(status)
    if args in (["--verify-portable"], ["--verify-portable", "--full-year"]):
        from verify_release import verify_portable

        raise SystemExit(verify_portable(full_year="--full-year" in args))
    if len(args) == 2 and args[0] in {"--desktop-smoke", "--desktop-smoke-year"}:
        from desktop import run

        raise SystemExit(run(smoke_output=Path(args[1]).resolve(), smoke_year=args[0].endswith("-year")))
    if args == ["--desktop"] or (not args and getattr(sys, "frozen", False)):
        from desktop import run

        raise SystemExit(run())
    if not args or args == ["--console"]:
        raise SystemExit(main())
    if len(args) == 3 and args[:2] == ["--console", "--quotes"]:
        raise SystemExit(main(Path(args[2])))
    raise SystemExit("Usage: launcher [--desktop | --console [--quotes FILE] | --verify-package | --verify-portable [--full-year]]")
