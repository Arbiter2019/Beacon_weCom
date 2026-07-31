from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from analysis_app.models import ConversationSnapshot, MessageDailyStats
from analysis_app.services.snapshot import build_daily_snapshot
from analysis_app.services.utils import MESSAGE_TYPE_KEYS, bump_type_count, copy_counts, empty_type_counts, utc_naive_range_for_beijing_day
from wecom_app.models import Message, MessageRecipient


def _conversation_messages(archive_db: Session, snapshot: ConversationSnapshot, start, end) -> list[Message]:
    stmt = select(Message).where(
        Message.is_recalled.is_(False),
        Message.msg_time >= start,
        Message.msg_time < end,
    )
    if snapshot.conversation_type == "single":
        stmt = (
            stmt.join(MessageRecipient, MessageRecipient.message_id == Message.id)
            .where(
                Message.conversation_type == "single",
                or_(
                    Message.sender_id == snapshot.observer_userid,
                    Message.sender_id == snapshot.external_userid,
                ),
                or_(
                    MessageRecipient.recipient_id == snapshot.observer_userid,
                    MessageRecipient.recipient_id == snapshot.external_userid,
                ),
            )
            .order_by(Message.msg_time, Message.id)
        )
    else:
        stmt = (
            stmt.where(
                Message.conversation_type == "room",
                Message.roomid == snapshot.roomid,
            )
            .order_by(Message.msg_time, Message.id)
        )
    return list(archive_db.scalars(stmt).all())


def _empty_stats_row(snapshot: ConversationSnapshot) -> MessageDailyStats:
    return MessageDailyStats(
        analysis_date=snapshot.analysis_date,
        observer_userid=snapshot.observer_userid,
        conversation_type=snapshot.conversation_type,
        external_userid=snapshot.external_userid,
        roomid=snapshot.roomid,
        display_name=snapshot.display_name,
        member_count=snapshot.member_count,
        received_count=0,
        sent_count=0,
        received_type_counts=empty_type_counts(),
        sent_type_counts=empty_type_counts(),
    )


def run_basic_stats(
    archive_db: Session,
    analysis_db: Session,
    analysis_date: date,
    observer_userid: str | None = None,
) -> dict:
    snapshot_stmt = select(ConversationSnapshot).where(ConversationSnapshot.analysis_date == analysis_date)
    if observer_userid:
        snapshot_stmt = snapshot_stmt.where(ConversationSnapshot.observer_userid == observer_userid)
    snapshots = list(analysis_db.scalars(snapshot_stmt.order_by(ConversationSnapshot.observer_userid)).all())
    if not snapshots:
        snapshots = build_daily_snapshot(archive_db, analysis_db, analysis_date, observer_userid)
        analysis_db.expire_all()

    analysis_db.execute(
        delete(MessageDailyStats).where(
            MessageDailyStats.analysis_date == analysis_date,
            MessageDailyStats.observer_userid.in_({snapshot.observer_userid for snapshot in snapshots} or {observer_userid}),
        )
    )
    analysis_db.commit()

    rows: list[MessageDailyStats] = []
    start, end = utc_naive_range_for_beijing_day(analysis_date)
    for snapshot in snapshots:
        messages = _conversation_messages(archive_db, snapshot, start, end)
        row = _empty_stats_row(snapshot)
        for message in messages:
            if snapshot.conversation_type == "single":
                direction = "sent" if message.sender_id == snapshot.observer_userid else "received"
            else:
                direction = "sent" if message.sender_type == "employee" else "received"
            if direction == "sent":
                row.sent_count += 1
                bump_type_count(row.sent_type_counts, message.msg_type)
            else:
                row.received_count += 1
                bump_type_count(row.received_type_counts, message.msg_type)
        rows.append(row)

    analysis_db.add_all(rows)
    analysis_db.commit()
    return {"rows_written": len(rows), "rows": rows}
