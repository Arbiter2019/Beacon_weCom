from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from analysis_app.models import ConversationSnapshot, ResponseHourlyStats
from analysis_app.services.snapshot import build_daily_snapshot
from analysis_app.services.utils import utc_naive_range_for_beijing_day
from analysis_app.time_utils import beijing_hour
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


def _sample_rows(snapshot: ConversationSnapshot) -> list[ResponseHourlyStats]:
    rows: list[ResponseHourlyStats] = []
    for hour in range(24):
        rows.append(
            ResponseHourlyStats(
                analysis_date=snapshot.analysis_date,
                observer_userid=snapshot.observer_userid,
                conversation_type=snapshot.conversation_type,
                external_userid=snapshot.external_userid,
                roomid=snapshot.roomid,
                display_name=snapshot.display_name,
                member_count=snapshot.member_count,
                hour=hour,
                response_avg_seconds=0,
                response_count=0,
            )
        )
    return rows


def run_response_stats(
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
        delete(ResponseHourlyStats).where(
            ResponseHourlyStats.analysis_date == analysis_date,
            ResponseHourlyStats.observer_userid.in_({snapshot.observer_userid for snapshot in snapshots} or {observer_userid}),
        )
    )
    analysis_db.commit()

    rows: list[ResponseHourlyStats] = []
    start, end = utc_naive_range_for_beijing_day(analysis_date)
    for snapshot in snapshots:
        messages = _conversation_messages(archive_db, snapshot, start, end)
        hour_totals: dict[int, list[int]] = defaultdict(list)
        previous_message: Message | None = None
        for message in messages:
            if previous_message is not None:
                if snapshot.conversation_type == "single":
                    is_employee = message.sender_id == snapshot.observer_userid
                    previous_external = previous_message.sender_id == snapshot.external_userid
                else:
                    is_employee = message.sender_type == "employee"
                    previous_external = previous_message.sender_type == "external_contact"
                if is_employee and previous_external:
                    hour_totals[beijing_hour(message.msg_time)].append(
                        int((message.msg_time - previous_message.msg_time).total_seconds())
                    )
            previous_message = message

        sample_rows = _sample_rows(snapshot)
        for row in sample_rows:
            samples = hour_totals.get(row.hour, [])
            if samples:
                row.response_count = len(samples)
                row.response_avg_seconds = int(sum(samples) / len(samples))
        rows.extend(sample_rows)

    analysis_db.add_all(rows)
    analysis_db.commit()
    return {"rows_written": len(rows), "rows": rows}
