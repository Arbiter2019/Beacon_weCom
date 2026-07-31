from datetime import date, datetime, timezone

from analysis_app.time_utils import beijing_date, beijing_hour, beijing_utc_range


def test_beijing_date_moves_utc_midnight_boundary_forward():
    assert beijing_date(datetime(2026, 7, 20, 16, 0, tzinfo=timezone.utc)) == date(2026, 7, 21)


def test_beijing_hour_uses_asia_shanghai_clock():
    assert beijing_hour(datetime(2026, 7, 20, 16, 59, 59, tzinfo=timezone.utc)) == 0


def test_beijing_utc_range_matches_one_local_day():
    start, end = beijing_utc_range(date(2026, 7, 21))

    assert start == datetime(2026, 7, 20, 16, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 7, 21, 16, 0, tzinfo=timezone.utc)
