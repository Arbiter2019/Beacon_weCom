from datetime import date

from analysis_app.models import ConversationSnapshot
from analysis_app.services.snapshot import build_daily_snapshot


def test_build_daily_snapshot_includes_private_and_group_conversations(db):
    rows = build_daily_snapshot(db, db, date(2026, 7, 21))

    assert len(rows) == 4
    private = [row for row in rows if row.conversation_type == "single"]
    room = [row for row in rows if row.conversation_type == "room"]
    assert {row.external_userid for row in private} == {"external_xiaoyu"}
    assert {row.roomid for row in room} == {"chat_math"}


def test_build_daily_snapshot_replaces_existing_rows(db):
    first = build_daily_snapshot(db, db, date(2026, 7, 21))
    second = build_daily_snapshot(db, db, date(2026, 7, 21))

    assert len(first) == len(second) == 4
    assert db.query(ConversationSnapshot).filter_by(analysis_date=date(2026, 7, 21)).count() == 4
