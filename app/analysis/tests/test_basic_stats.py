from datetime import date

from analysis_app.services.basic_stats import run_basic_stats


def test_basic_stats_counts_private_and_group_messages_for_observer(db):
    result = run_basic_stats(db, db, date(2026, 7, 21), observer_userid="wang_teacher")

    assert result["rows_written"] == 2
    private = next(row for row in result["rows"] if row.conversation_type == "single")
    room = next(row for row in result["rows"] if row.conversation_type == "room")
    assert private.sent_count == 1
    assert private.received_count == 1
    assert room.sent_count == 2
    assert room.received_count == 2
    assert room.sent_type_counts["text"] == 2


def test_basic_stats_persists_zero_counts_for_empty_conversation_rows(db):
    result = run_basic_stats(db, db, date(2026, 7, 21), observer_userid="li_teacher")

    private = next(row for row in result["rows"] if row.conversation_type == "single")
    assert private.sent_count == 0
    assert private.received_count == 0
