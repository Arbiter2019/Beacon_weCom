from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from math import ceil
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from analysis_app.models import (
    HotwordDailyStats,
    MessageDailyStats,
    QuestionDetail,
    SentimentDailyStats,
)
from analysis_app.question_categories import load_question_categories
from analysis_app.services.utils import MESSAGE_TYPE_KEYS, utc_naive_range_for_beijing_day
from wecom_app.api.deps import require_admin, require_observable_userid
from wecom_app.db.analysis_session import get_analysis_db
from wecom_app.db.session import get_db
from wecom_app.models import CustomerChat, CustomerChatMember, Employee, Message

MIN_ANALYSIS_DATE = date(2026, 7, 20)
QUESTION_EXCLUDED = "uncategorized"

analysis_router = APIRouter(prefix="/api/analysis", dependencies=[Depends(require_admin)])
employee_router = APIRouter(
    prefix="/api/analysis/observed-employees/{userid}",
    dependencies=[Depends(require_admin), Depends(require_observable_userid)],
)


def _validate_dates(start_date: date, end_date: date) -> None:
    if start_date < MIN_ANALYSIS_DATE or end_date < MIN_ANALYSIS_DATE:
        raise HTTPException(status_code=422, detail="analysis date cannot be earlier than 2026-07-20")
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date cannot be later than end_date")


def _category_labels() -> dict[str, str]:
    return {item.key: item.label for item in load_question_categories()}


def _empty_type_counts() -> dict[str, int]:
    return {key: 0 for key in MESSAGE_TYPE_KEYS}


def _merge_type_counts(target: dict[str, dict[str, int]], received: dict | None, sent: dict | None) -> None:
    for key in MESSAGE_TYPE_KEYS:
        target[key]["received_count"] += int((received or {}).get(key, 0) or 0)
        target[key]["sent_count"] += int((sent or {}).get(key, 0) or 0)


def _date_list(start_date: date, end_date: date) -> list[date]:
    days = (end_date - start_date).days
    return [date.fromordinal(start_date.toordinal() + offset) for offset in range(days + 1)]


def _seconds_percentile(samples: list[int], percentile: float) -> int:
    if not samples:
        return 0
    ordered = sorted(samples)
    index = max(0, min(len(ordered) - 1, ceil(percentile * len(ordered)) - 1))
    return int(ordered[index])


def _response_summary(samples: list[int]) -> dict[str, int]:
    if not samples:
        return {
            "avg_seconds": 0,
            "median_seconds": 0,
            "q1_seconds": 0,
            "q3_seconds": 0,
            "min_seconds": 0,
            "max_seconds": 0,
            "sample_count": 0,
        }
    return {
        "avg_seconds": int(sum(samples) / len(samples)),
        "median_seconds": _seconds_percentile(samples, 0.5),
        "q1_seconds": _seconds_percentile(samples, 0.25),
        "q3_seconds": _seconds_percentile(samples, 0.75),
        "min_seconds": int(min(samples)),
        "max_seconds": int(max(samples)),
        "sample_count": len(samples),
    }


def _room_response_samples(archive_db: Session, roomid: str, analysis_date: date) -> list[int]:
    start, end = utc_naive_range_for_beijing_day(analysis_date)
    stmt = (
        select(Message)
        .where(
            Message.conversation_type == "room",
            Message.roomid == roomid,
            Message.msg_time >= start,
            Message.msg_time < end,
            Message.is_recalled.is_(False),
        )
        .order_by(Message.msg_time, Message.id)
    )
    samples: list[int] = []
    previous: Message | None = None
    for message in archive_db.scalars(stmt):
        if previous is not None and message.sender_type == "employee" and previous.sender_type == "external_contact":
            samples.append(int((message.msg_time - previous.msg_time).total_seconds()))
        previous = message
    return samples


def _visible_roomids(archive_db: Session, observer_userid: str) -> set[str]:
    stmt = (
        select(CustomerChat.chat_id)
        .join(CustomerChatMember, CustomerChatMember.chat_id == CustomerChat.chat_id)
        .where(
            CustomerChatMember.member_userid == observer_userid,
            CustomerChatMember.is_active.is_(True),
            CustomerChat.status == "active",
        )
    )
    return set(archive_db.scalars(stmt).all())


def _require_visible_room(archive_db: Session, observer_userid: str, roomid: str) -> None:
    if roomid not in _visible_roomids(archive_db, observer_userid):
        raise HTTPException(status_code=403, detail="room is not visible to observer")


def _employee_name(archive_db: Session, userid: str | None) -> str | None:
    if not userid:
        return None
    employee = archive_db.scalar(select(Employee).where(Employee.userid == userid))
    return employee.name if employee and employee.name else userid


def _question_base_stmt(userid: str, start_date: date, end_date: date):
    return select(QuestionDetail).where(
        QuestionDetail.observer_userid == userid,
        QuestionDetail.analysis_date >= start_date,
        QuestionDetail.analysis_date <= end_date,
        QuestionDetail.is_question.is_(True),
        QuestionDetail.question_category != QUESTION_EXCLUDED,
    )


def _question_out(row: QuestionDetail, labels: dict[str, str]) -> dict:
    return {
        "id": row.id,
        "analysis_date": row.analysis_date.isoformat(),
        "msgid": row.msgid,
        "content_text": row.content_text,
        "question_category": row.question_category,
        "question_category_name": labels.get(row.question_category, row.question_category),
        "sender_external_userid": row.sender_external_userid,
        "sender_display_name": row.sender_group_remark or row.sender_wechat_name or row.sender_external_userid,
        "roomid": row.roomid,
        "room_name": row.room_name,
        "msg_time": row.created_at.strftime("%Y-%m-%d %H:%M:%S") if isinstance(row.created_at, datetime) else None,
    }


def _paginate(items: list[dict], page: int, page_size: int) -> dict:
    start = (page - 1) * page_size
    end = start + page_size
    return {"items": items[start:end], "total": len(items), "page": page, "page_size": page_size}


def _sort_items(items: list[dict], sort: str, order: Literal["asc", "desc"], allowed: set[str]) -> list[dict]:
    if sort not in allowed:
        raise HTTPException(status_code=422, detail=f"unsupported sort field: {sort}")
    reverse = order == "desc"
    return sorted(items, key=lambda item: (item.get(sort) is None, item.get(sort)), reverse=reverse)


def _summary_payload(
    archive_db: Session,
    analysis_db: Session,
    userid: str,
    start_date: date,
    end_date: date,
    conversation_type: Literal["all", "single", "room"],
    roomid: str | None = None,
) -> dict:
    labels = _category_labels()
    stmt = select(MessageDailyStats).where(
        MessageDailyStats.observer_userid == userid,
        MessageDailyStats.analysis_date >= start_date,
        MessageDailyStats.analysis_date <= end_date,
    )
    if conversation_type != "all":
        stmt = stmt.where(MessageDailyStats.conversation_type == conversation_type)
    if roomid:
        stmt = stmt.where(MessageDailyStats.conversation_type == "room", MessageDailyStats.roomid == roomid)

    message_rows = list(analysis_db.scalars(stmt).all())
    message_by_date: dict[date, dict[str, int]] = {
        day: {
            "analysis_date": day.isoformat(),
            "single_received_count": 0,
            "single_sent_count": 0,
            "room_received_count": 0,
            "room_sent_count": 0,
            "received_count": 0,
            "sent_count": 0,
        }
        for day in _date_list(start_date, end_date)
    }
    type_counts = {key: {"msg_type": key, "received_count": 0, "sent_count": 0} for key in MESSAGE_TYPE_KEYS}
    overview = {
        "single_message_count": 0,
        "room_message_count": 0,
        "received_message_count": 0,
        "sent_message_count": 0,
        "question_count": 0,
        "avg_response_seconds": 0,
    }
    for row in message_rows:
        received = int(row.received_count or 0)
        sent = int(row.sent_count or 0)
        total = received + sent
        bucket = message_by_date[row.analysis_date]
        bucket["received_count"] += received
        bucket["sent_count"] += sent
        if row.conversation_type == "single":
            overview["single_message_count"] += total
            bucket["single_received_count"] += received
            bucket["single_sent_count"] += sent
        elif row.conversation_type == "room":
            overview["room_message_count"] += total
            bucket["room_received_count"] += received
            bucket["room_sent_count"] += sent
        overview["received_message_count"] += received
        overview["sent_message_count"] += sent
        _merge_type_counts(type_counts, row.received_type_counts, row.sent_type_counts)

    sentiment_stmt = select(SentimentDailyStats).where(
        SentimentDailyStats.observer_userid == userid,
        SentimentDailyStats.analysis_date >= start_date,
        SentimentDailyStats.analysis_date <= end_date,
    )
    if roomid:
        sentiment_stmt = sentiment_stmt.where(SentimentDailyStats.roomid == roomid)
    sentiment_counter = Counter()
    roomids: set[str] = set()
    for row in analysis_db.scalars(sentiment_stmt):
        sentiment_counter["positive"] += row.positive_count
        sentiment_counter["neutral"] += row.neutral_count
        sentiment_counter["negative"] += row.negative_count
        sentiment_counter["total"] += row.total_count
        roomids.add(row.roomid)

    hotword_stmt = select(HotwordDailyStats).where(
        HotwordDailyStats.observer_userid == userid,
        HotwordDailyStats.analysis_date >= start_date,
        HotwordDailyStats.analysis_date <= end_date,
    )
    if roomid:
        hotword_stmt = hotword_stmt.where(HotwordDailyStats.roomid == roomid)
    hotwords = Counter()
    for row in analysis_db.scalars(hotword_stmt):
        roomids.add(row.roomid)
        for item in row.hotwords or []:
            hotwords[str(item.get("word", ""))] += int(item.get("count", 0) or 0)

    question_stmt = _question_base_stmt(userid, start_date, end_date)
    if roomid:
        question_stmt = question_stmt.where(QuestionDetail.roomid == roomid)
    question_counts = Counter()
    for row in analysis_db.scalars(question_stmt):
        question_counts[row.question_category] += 1
    overview["question_count"] = sum(question_counts.values())

    response_daily_stats = []
    response_all_samples: list[int] = []
    response_roomids = sorted(
        {
            row.roomid
            for row in message_rows
            if row.conversation_type == "room" and row.roomid and (roomid is None or row.roomid == roomid)
        }
    )
    for day in _date_list(start_date, end_date):
        day_samples: list[int] = []
        for response_roomid in response_roomids:
            day_samples.extend(_room_response_samples(archive_db, response_roomid, day))
        response_all_samples.extend(day_samples)
        response_daily_stats.append({"analysis_date": day.isoformat(), **_response_summary(day_samples)})
    overview["avg_response_seconds"] = _response_summary(response_all_samples)["avg_seconds"]

    return {
        "overview": overview,
        "message_trend": list(message_by_date.values()),
        "message_type_distribution": list(type_counts.values()),
        "sentiment_summary": {
            "positive_count": sentiment_counter["positive"],
            "neutral_count": sentiment_counter["neutral"],
            "negative_count": sentiment_counter["negative"],
            "total_count": sentiment_counter["total"],
            "covered_room_count": len(roomids),
        },
        "hotwords": [{"word": word, "count": count} for word, count in hotwords.most_common(20) if word],
        "question_category_stats": [
            {"code": code, "display_name": labels.get(code, code), "count": count}
            for code, count in sorted(question_counts.items(), key=lambda item: labels.get(item[0], item[0]))
        ],
        "response_daily_stats": response_daily_stats,
    }


@analysis_router.get("/question-categories", response_model=dict)
def question_categories() -> dict:
    return {
        "items": [
            {"code": item.key, "display_name": item.label, "sort_order": index + 1, "enabled": True}
            for index, item in enumerate(load_question_categories())
            if item.key != QUESTION_EXCLUDED
        ]
    }


@employee_router.get("/summary", response_model=dict)
def observed_employee_summary(
    userid: str,
    start_date: date,
    end_date: date,
    conversation_type: Literal["all", "single", "room"] = "all",
    archive_db: Session = Depends(get_db),
    analysis_db: Session = Depends(get_analysis_db),
) -> dict:
    _validate_dates(start_date, end_date)
    return _summary_payload(archive_db, analysis_db, userid, start_date, end_date, conversation_type)


@employee_router.get("/questions", response_model=dict)
def observed_employee_questions(
    userid: str,
    start_date: date,
    end_date: date,
    question_categories: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort: Literal["msg_time", "analysis_date", "question_category", "room_name"] = "msg_time",
    order: Literal["asc", "desc"] = "desc",
    analysis_db: Session = Depends(get_analysis_db),
) -> dict:
    _validate_dates(start_date, end_date)
    labels = _category_labels()
    stmt = _question_base_stmt(userid, start_date, end_date)
    categories = [item for item in question_categories.split(",") if item]
    if categories:
        stmt = stmt.where(QuestionDetail.question_category.in_(categories))
    rows = [_question_out(row, labels) for row in analysis_db.scalars(stmt).all()]
    sort_key = "analysis_date" if sort == "msg_time" else sort
    rows = _sort_items(rows, sort_key, order, {"analysis_date", "question_category", "room_name"})
    return _paginate(rows, page, page_size)


@employee_router.get("/response-groups", response_model=dict)
def observed_employee_response_groups(
    userid: str,
    start_date: date,
    end_date: date,
    room_name: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort: Literal["analysis_date", "room_name", "avg", "median", "q1", "q3", "max", "min"] = "analysis_date",
    order: Literal["asc", "desc"] = "desc",
    archive_db: Session = Depends(get_db),
    analysis_db: Session = Depends(get_analysis_db),
) -> dict:
    _validate_dates(start_date, end_date)
    stmt = (
        select(MessageDailyStats.analysis_date, MessageDailyStats.roomid, MessageDailyStats.display_name)
        .where(
            MessageDailyStats.observer_userid == userid,
            MessageDailyStats.conversation_type == "room",
            MessageDailyStats.analysis_date >= start_date,
            MessageDailyStats.analysis_date <= end_date,
            MessageDailyStats.roomid.is_not(None),
        )
        .group_by(MessageDailyStats.analysis_date, MessageDailyStats.roomid, MessageDailyStats.display_name)
    )
    if room_name:
        stmt = stmt.where(MessageDailyStats.display_name.like(f"%{room_name}%"))
    items: list[dict] = []
    for day, roomid, display_name in analysis_db.execute(stmt).all():
        summary = _response_summary(_room_response_samples(archive_db, roomid, day))
        items.append({"analysis_date": day.isoformat(), "roomid": roomid, "room_name": display_name, **summary})
    sort_map = {
        "avg": "avg_seconds",
        "median": "median_seconds",
        "q1": "q1_seconds",
        "q3": "q3_seconds",
        "max": "max_seconds",
        "min": "min_seconds",
        "analysis_date": "analysis_date",
        "room_name": "room_name",
    }
    items = _sort_items(items, sort_map[sort], order, set(sort_map.values()))
    if sort == "analysis_date":
        items = sorted(items, key=lambda item: (item["analysis_date"], item["room_name"]), reverse=(order == "desc"))
    return _paginate(items, page, page_size)


@analysis_router.get("/customer-chats", response_model=dict)
def customer_chats(
    observer_userid: str,
    keyword: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    archive_db: Session = Depends(get_db),
) -> dict:
    visible_roomids = _visible_roomids(archive_db, observer_userid)
    if not visible_roomids:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}
    stmt = select(CustomerChat).where(CustomerChat.chat_id.in_(visible_roomids))
    if keyword:
        stmt = stmt.where(or_(CustomerChat.name.like(f"%{keyword}%"), CustomerChat.chat_id.like(f"%{keyword}%")))
    items = []
    for chat in archive_db.scalars(stmt.order_by(CustomerChat.name, CustomerChat.chat_id)):
        items.append(
            {
                "roomid": chat.chat_id,
                "room_name": chat.name or chat.chat_id,
                "member_count": chat.member_count,
                "owner_userid": chat.owner_userid,
                "owner_name": _employee_name(archive_db, chat.owner_userid),
            }
        )
    return _paginate(items, page, page_size)


@analysis_router.get("/customer-chats/{roomid}/summary", response_model=dict)
def customer_chat_summary(
    roomid: str,
    observer_userid: str,
    start_date: date,
    end_date: date,
    archive_db: Session = Depends(get_db),
    analysis_db: Session = Depends(get_analysis_db),
) -> dict:
    _validate_dates(start_date, end_date)
    _require_visible_room(archive_db, observer_userid, roomid)
    return _summary_payload(archive_db, analysis_db, observer_userid, start_date, end_date, "room", roomid=roomid)


@analysis_router.get("/customer-chats/{roomid}/questions", response_model=dict)
def customer_chat_questions(
    roomid: str,
    observer_userid: str,
    start_date: date,
    end_date: date,
    question_categories: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort: Literal["msg_time", "analysis_date", "question_category", "room_name"] = "msg_time",
    order: Literal["asc", "desc"] = "desc",
    archive_db: Session = Depends(get_db),
    analysis_db: Session = Depends(get_analysis_db),
) -> dict:
    _validate_dates(start_date, end_date)
    _require_visible_room(archive_db, observer_userid, roomid)
    labels = _category_labels()
    stmt = _question_base_stmt(observer_userid, start_date, end_date).where(QuestionDetail.roomid == roomid)
    categories = [item for item in question_categories.split(",") if item]
    if categories:
        stmt = stmt.where(QuestionDetail.question_category.in_(categories))
    rows = [_question_out(row, labels) for row in analysis_db.scalars(stmt).all()]
    sort_key = "analysis_date" if sort == "msg_time" else sort
    rows = _sort_items(rows, sort_key, order, {"analysis_date", "question_category", "room_name"})
    return _paginate(rows, page, page_size)
