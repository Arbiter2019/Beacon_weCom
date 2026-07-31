from __future__ import annotations

from datetime import date, datetime

from analysis_app.time_utils import beijing_utc_range

MESSAGE_TYPE_KEYS = ("text", "image", "voice", "video", "emotion", "file", "weapp")


def utc_naive_range_for_beijing_day(day: date) -> tuple[datetime, datetime]:
    start, end = beijing_utc_range(day)
    return start.replace(tzinfo=None), end.replace(tzinfo=None)


def empty_type_counts() -> dict[str, int]:
    return {key: 0 for key in MESSAGE_TYPE_KEYS}


def bump_type_count(counts: dict[str, int], msg_type: str | None) -> None:
    if msg_type in counts:
        counts[msg_type] += 1


def copy_counts(counts: dict[str, int]) -> dict[str, int]:
    return {key: int(value) for key, value in counts.items()}


def floor_seconds(delta: float) -> int:
    return int(delta // 1)
