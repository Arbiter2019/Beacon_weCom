from datetime import date

from analysis_app.services.response_stats import run_response_stats


def test_response_stats_counts_group_replies_from_any_employee(db):
    result = run_response_stats(db, db, date(2026, 7, 21), observer_userid="wang_teacher")

    rows = result["rows"]
    assert len(rows) == 48
    hour_7 = next(row for row in rows if row.conversation_type == "room" and row.hour == 7)
    hour_9 = next(row for row in rows if row.conversation_type == "single" and row.hour == 0)
    hour_10 = next(row for row in rows if row.conversation_type == "room" and row.hour == 10)
    assert hour_7.response_count == 1
    assert hour_7.response_avg_seconds == 420
    assert hour_10.response_count == 1
    assert hour_10.response_avg_seconds == 2100
    assert hour_9.response_count == 1
    assert hour_9.response_avg_seconds == 600


def test_response_stats_returns_24_rows_per_snapshot_conversation(db):
    result = run_response_stats(db, db, date(2026, 7, 21), observer_userid="wang_teacher")

    per_conversation = {}
    for row in result["rows"]:
        per_conversation.setdefault((row.conversation_type, row.external_userid or row.roomid), 0)
        per_conversation[(row.conversation_type, row.external_userid or row.roomid)] += 1

    assert per_conversation[("single", "external_xiaoyu")] == 24
    assert per_conversation[("room", "chat_math")] == 24
