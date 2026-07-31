from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

BEIJING_TZ = timezone(timedelta(hours=8))


def _to_beijing(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BEIJING_TZ)


def beijing_date(dt: datetime) -> date:
    return _to_beijing(dt).date()


def beijing_hour(dt: datetime) -> int:
    return _to_beijing(dt).hour


def beijing_utc_range(day: date) -> tuple[datetime, datetime]:
    start_local = datetime.combine(day, time.min, tzinfo=BEIJING_TZ)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

