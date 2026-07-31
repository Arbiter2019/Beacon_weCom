from __future__ import annotations

from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from analysis_app.models import ConversationSnapshot, QuestionDetail
from analysis_app.prompts import build_question_prompt
from analysis_app.question_categories import load_question_categories
from analysis_app.services.snapshot import build_daily_snapshot
from analysis_app.services.utils import utc_naive_range_for_beijing_day
from wecom_app.models import Message

_VALID_CATEGORIES = {item.key for item in load_question_categories()}


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


def run_question_classification(
    archive_db: Session,
    analysis_db: Session,
    analysis_date: date,
    llm_client,
    observer_userid: str | None = None,
) -> dict:
    snapshots = _ensure_snapshots(archive_db, analysis_db, analysis_date, observer_userid)
    if not snapshots:
        return {"rows_written": 0, "rows": []}

    analysis_db.execute(
        delete(QuestionDetail).where(
            QuestionDetail.analysis_date == analysis_date,
            QuestionDetail.observer_userid.in_({snapshot.observer_userid for snapshot in snapshots} or {observer_userid}),
        )
    )
    analysis_db.commit()

    start, end = utc_naive_range_for_beijing_day(analysis_date)
    prompt = build_question_prompt()
    rows: list[QuestionDetail] = []

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
            continue

        response = llm_client.analyze_questions(prompt, payload)
        items = response.get("items", []) if isinstance(response, dict) else []
        for item in items:
            category = item.get("category", "uncategorized")
            if category not in _VALID_CATEGORIES:
                raise ValueError(f"invalid question category: {category}")
            rows.append(
                QuestionDetail(
                    analysis_date=analysis_date,
                    observer_userid=snapshot.observer_userid,
                    roomid=snapshot.roomid or "",
                    room_name=snapshot.display_name,
                    member_count=snapshot.member_count,
                    msgid=item.get("msgid", ""),
                    content_text=item.get("content_text") or next(
                        (message.content_text or "" for message in messages if message.msgid == item.get("msgid")),
                        "",
                    ),
                    sender_external_userid=item.get("sender_external_userid")
                    or next((message.sender_id for message in messages if message.msgid == item.get("msgid")), ""),
                    sender_wechat_name=item.get("sender_wechat_name")
                    or next((message.sender_name for message in messages if message.msgid == item.get("msgid")), None),
                    sender_group_remark=item.get("sender_group_remark"),
                    is_question=bool(item.get("is_question", False)),
                    question_category=category,
                    llm_output={"raw": response, "item": item},
                    error=None,
                )
            )

    analysis_db.add_all(rows)
    analysis_db.commit()
    return {"rows_written": len(rows), "rows": rows}

