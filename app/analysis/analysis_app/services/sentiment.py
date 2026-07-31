from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from analysis_app.models import ConversationSnapshot, SentimentDailyStats, SentimentDetail
from analysis_app.prompts import build_sentiment_prompt
from analysis_app.services.snapshot import build_daily_snapshot
from analysis_app.services.utils import utc_naive_range_for_beijing_day
from wecom_app.models import Message

_VALID_SENTIMENTS = {"positive", "neutral", "negative"}


def _room_messages(archive_db: Session, snapshot: ConversationSnapshot, start, end) -> list[Message]:
    stmt = (
        select(Message)
        .where(
            Message.conversation_type == "room",
            Message.roomid == snapshot.roomid,
            Message.msg_time >= start,
            Message.msg_time < end,
            Message.is_recalled.is_(False),
            Message.sender_type == "external_contact",
            Message.msg_type == "text",
        )
        .order_by(Message.msg_time, Message.id)
    )
    return list(archive_db.scalars(stmt).all())


def _ensure_snapshots(
    archive_db: Session,
    analysis_db: Session,
    analysis_date: date,
    observer_userid: str | None,
) -> list[ConversationSnapshot]:
    stmt = select(ConversationSnapshot).where(
        ConversationSnapshot.analysis_date == analysis_date,
        ConversationSnapshot.conversation_type == "room",
    )
    if observer_userid:
        stmt = stmt.where(ConversationSnapshot.observer_userid == observer_userid)
    snapshots = list(analysis_db.scalars(stmt).all())
    if snapshots:
        return snapshots
    snapshots = build_daily_snapshot(archive_db, analysis_db, analysis_date, observer_userid)
    return [snapshot for snapshot in snapshots if snapshot.conversation_type == "room"]


def run_sentiment_analysis(
    archive_db: Session,
    analysis_db: Session,
    analysis_date: date,
    llm_client,
    observer_userid: str | None = None,
) -> dict:
    snapshots = _ensure_snapshots(archive_db, analysis_db, analysis_date, observer_userid)
    if not snapshots:
        return {"detail_rows_written": 0, "daily_rows_written": 0, "detail_rows": [], "daily_rows": []}

    analysis_db.execute(
        delete(SentimentDetail).where(
            SentimentDetail.analysis_date == analysis_date,
            SentimentDetail.observer_userid.in_({snapshot.observer_userid for snapshot in snapshots} or {observer_userid}),
        )
    )
    analysis_db.execute(
        delete(SentimentDailyStats).where(
            SentimentDailyStats.analysis_date == analysis_date,
            SentimentDailyStats.observer_userid.in_({snapshot.observer_userid for snapshot in snapshots} or {observer_userid}),
        )
    )
    analysis_db.commit()

    start, end = utc_naive_range_for_beijing_day(analysis_date)
    prompt = build_sentiment_prompt()
    detail_rows: list[SentimentDetail] = []
    daily_rows: list[SentimentDailyStats] = []

    for snapshot in snapshots:
        messages = _room_messages(archive_db, snapshot, start, end)
        payload = [
            {
                "msgid": message.msgid,
                "content_text": message.content_text or "",
                "sender_external_userid": message.sender_id,
                "sender_wechat_name": message.sender_name,
                "sender_group_remark": None,
            }
            for message in messages
        ]
        if not payload:
            daily_rows.append(
                SentimentDailyStats(
                    analysis_date=analysis_date,
                    observer_userid=snapshot.observer_userid,
                    roomid=snapshot.roomid or "",
                    room_name=snapshot.display_name,
                    member_count=snapshot.member_count,
                    positive_count=0,
                    neutral_count=0,
                    negative_count=0,
                    total_count=0,
                )
            )
            continue

        response = llm_client.analyze_sentiment(prompt, payload)
        items = response.get("items", []) if isinstance(response, dict) else []
        counts = Counter()
        for item in items:
            sentiment = item.get("sentiment")
            if sentiment not in _VALID_SENTIMENTS:
                continue
            counts[sentiment] += 1
            detail_rows.append(
                SentimentDetail(
                    analysis_date=analysis_date,
                    observer_userid=snapshot.observer_userid,
                    roomid=snapshot.roomid or "",
                    room_name=snapshot.display_name,
                    member_count=snapshot.member_count,
                    msgid=item.get("msgid", ""),
                    sentiment=sentiment,
                    llm_output={"raw": response, "item": item},
                    error=None,
                )
            )
        daily_rows.append(
            SentimentDailyStats(
                analysis_date=analysis_date,
                observer_userid=snapshot.observer_userid,
                roomid=snapshot.roomid or "",
                room_name=snapshot.display_name,
                member_count=snapshot.member_count,
                positive_count=counts["positive"],
                neutral_count=counts["neutral"],
                negative_count=counts["negative"],
                total_count=sum(counts.values()),
            )
        )

    analysis_db.add_all(detail_rows + daily_rows)
    analysis_db.commit()
    return {
        "detail_rows_written": len(detail_rows),
        "daily_rows_written": len(daily_rows),
        "detail_rows": detail_rows,
        "daily_rows": daily_rows,
    }

