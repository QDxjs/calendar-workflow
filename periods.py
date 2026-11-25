import calendar
from datetime import date, timedelta


def dates_between(start: date, end: date) -> list[date]:
    if end < start:
        raise ValueError("结束日期不能早于开始日期。")
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def dates_in_iso_week(target: date) -> list[date]:
    iso_year, iso_week, _ = target.isocalendar()
    monday = date.fromisocalendar(iso_year, iso_week, 1)
    try:
        return [monday + timedelta(days=offset) for offset in range(7)]
    except OverflowError as exc:
        raise ValueError("该 ISO 周超出可表示的公历日期范围，请选择其他日期。") from exc


def dates_in_month(year: int, month: int) -> list[date]:
    first_day = date(year, month, 1)
    day_count = calendar.monthrange(year, month)[1]
    return [first_day + timedelta(days=offset) for offset in range(day_count)]


def dates_in_year(year: int) -> list[date]:
    first_day = date(year, 1, 1)
    day_count = 366 if calendar.isleap(year) else 365
    return [first_day + timedelta(days=offset) for offset in range(day_count)]
