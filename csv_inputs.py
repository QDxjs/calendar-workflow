"""Validated CSV input helpers for calendar generation and replay."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
import re


def read_rows(path: Path, *, extra_required: tuple[str, ...] = ()) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"找不到内容表：{path}")
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source_file:
            reader = csv.DictReader(source_file, strict=True)
            fieldnames = reader.fieldnames or []
            if any(not name or not name.strip() for name in fieldnames):
                raise ValueError("CSV 表头含有空字段名。")
            normalized_names = [name.strip() for name in fieldnames]
            if len(normalized_names) != len(set(normalized_names)):
                raise ValueError("CSV 表头含有重复字段名。")
            reader.fieldnames = normalized_names
            required = {"date", "quote", "source", "layout", *extra_required}
            missing = required - set(normalized_names)
            if missing:
                raise ValueError("CSV 缺少字段：" + ", ".join(sorted(missing)))
            rows = []
            for row_number, row in enumerate(reader, start=2):
                if None in row:
                    raise ValueError(f"CSV 第 {row_number} 条记录（表头为第 1 条）包含多余字段，请检查逗号或表头。")
                absent = [name for name in normalized_names if row[name] is None]
                if absent:
                    raise ValueError(
                        f"CSV 第 {row_number} 条记录（表头为第 1 条）缺少字段：{', '.join(absent)}。"
                        "若字段无需填写，请保留逗号占位。"
                    )
                rows.append(row)
    except csv.Error as exc:
        raise ValueError(f"CSV 格式无效：{exc}") from exc
    if not rows:
        raise ValueError("内容表没有数据行。")
    return rows


def parse_csv_date(raw_date: str, record_number: int) -> date:
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw_date):
        raise ValueError(f"第 {record_number} 条记录日期格式无效：{raw_date!r}；请使用 YYYY-MM-DD。")
    try:
        return date.fromisoformat(raw_date)
    except ValueError as exc:
        raise ValueError(f"第 {record_number} 条记录日期不存在：{raw_date!r}") from exc
