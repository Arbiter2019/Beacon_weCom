from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from analysis_app.models import (
    HotwordDailyStats,
    MessageDailyStats,
    QuestionDetail,
    ResponseHourlyStats,
    SentimentDailyStats,
    TaskRun,
)
from analysis_app.question_categories import load_question_categories
from wecom_app.core.config import Settings, get_settings
from wecom_app.db.analysis_session import get_analysis_db
from wecom_app.db.session import get_db
from wecom_app.models import Message

BEIJING = ZoneInfo("Asia/Shanghai")
UTC = ZoneInfo("UTC")
ARCHIVE_MAX_LIMIT = 10_000
QUESTION_EXCLUDED = "uncategorized"

router = APIRouter(prefix="/api/chatbi", tags=["chatbi"])


def require_chatbi_token(
    x_chatbi_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> str:
    if not x_chatbi_token or x_chatbi_token != settings.chatbi_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid chatbi token")
    return "chatbi"


def _meta(
    datasource: Literal["analysis", "archive"],
    row_count: int,
    *,
    request_id: str,
    sql: str,
    chart_hint: str | None = None,
    truncated: bool = False,
    limit: int | None = None,
    fallback_used: bool = False,
    latest_analysis_date: str | None = None,
) -> dict:
    meta = {
        "datasource": datasource,
        "row_count": row_count,
        "truncated": truncated,
        "executed_at": datetime.now(BEIJING).isoformat(timespec="seconds"),
        "fallback_used": fallback_used,
    }
    if datasource == "analysis":
        meta["data_freshness"] = "T+1"
    if latest_analysis_date:
        meta["latest_analysis_date"] = latest_analysis_date
    if chart_hint:
        meta["chart_hint"] = chart_hint
    if limit is not None:
        meta["limit"] = limit
    return {"request_id": request_id, "sql": sql, "rows": [], "meta": meta}


def _response(request_id: str, sql: str, rows: list[dict], meta: dict) -> dict:
    return {"request_id": request_id, "sql": sql, "rows": rows, "meta": meta}


def _latest_analysis_date(analysis_db: Session) -> date | None:
    return analysis_db.scalar(
        select(func.max(TaskRun.analysis_date)).where(TaskRun.status == "success")
    )


def _labels() -> dict[str, str]:
    return {item.key: item.label for item in load_question_categories()}


def _archive_limit(value: int) -> int:
    return max(1, min(value, ARCHIVE_MAX_LIMIT))


def _beijing_naive_to_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=BEIJING)
    return value.astimezone(UTC).replace(tzinfo=None)


def _utc_naive_to_beijing(value: datetime) -> str:
    return value.replace(tzinfo=UTC).astimezone(BEIJING).isoformat(timespec="seconds")


@router.get("/freshness", dependencies=[Depends(require_chatbi_token)])
def freshness(
    request_id: str = "chatbi_freshness",
    analysis_db: Session = Depends(get_analysis_db),
) -> dict:
    latest = _latest_analysis_date(analysis_db)
    latest_text = latest.isoformat() if latest else None
    sql = "select max(analysis_date) as latest_analysis_date from analysis_task_run where status = 'success'"
    rows = [{"latest_analysis_date": latest_text, "data_freshness": "T+1"}]
    base = _meta(
        "analysis",
        len(rows),
        request_id=request_id,
        sql=sql,
        latest_analysis_date=latest_text,
    )
    return _response(request_id, sql, rows, base["meta"])


@router.get("/message-volume", dependencies=[Depends(require_chatbi_token)])
def message_volume(
    start_date: date,
    end_date: date,
    request_id: str = "chatbi_message_volume",
    conversation_type: Literal["all", "single", "room"] = "all",
    analysis_db: Session = Depends(get_analysis_db),
) -> dict:
    sql = (
        "select analysis_date, conversation_type, sum(received_count), sum(sent_count) "
        "from analysis_message_daily_stats where analysis_date between :start_date and :end_date"
    )
    stmt = (
        select(
            MessageDailyStats.analysis_date,
            MessageDailyStats.conversation_type,
            func.sum(MessageDailyStats.received_count).label("received_count"),
            func.sum(MessageDailyStats.sent_count).label("sent_count"),
        )
        .where(MessageDailyStats.analysis_date >= start_date, MessageDailyStats.analysis_date <= end_date)
        .group_by(MessageDailyStats.analysis_date, MessageDailyStats.conversation_type)
        .order_by(MessageDailyStats.analysis_date, MessageDailyStats.conversation_type)
    )
    if conversation_type != "all":
        stmt = stmt.where(MessageDailyStats.conversation_type == conversation_type)
        sql += " and conversation_type = :conversation_type"
    sql += " group by analysis_date, conversation_type order by analysis_date, conversation_type"
    rows = []
    for row in analysis_db.execute(stmt).all():
        received = int(row.received_count or 0)
        sent = int(row.sent_count or 0)
        rows.append(
            {
                "analysis_date": row.analysis_date.isoformat(),
                "conversation_type": row.conversation_type,
                "received_count": received,
                "sent_count": sent,
                "total_count": received + sent,
            }
        )
    base = _meta("analysis", len(rows), request_id=request_id, sql=sql, chart_hint="line")
    return _response(request_id, sql, rows, base["meta"])


@router.get("/response-time", dependencies=[Depends(require_chatbi_token)])
def response_time(
    start_date: date,
    end_date: date,
    request_id: str = "chatbi_response_time",
    conversation_type: Literal["all", "single", "room"] = "all",
    analysis_db: Session = Depends(get_analysis_db),
) -> dict:
    sql = (
        "select analysis_date, hour, sum(response_avg_seconds * response_count) / sum(response_count), "
        "sum(response_count) from analysis_response_hourly_stats"
    )
    stmt = (
        select(
            ResponseHourlyStats.analysis_date,
            ResponseHourlyStats.hour,
            func.sum(ResponseHourlyStats.response_avg_seconds * ResponseHourlyStats.response_count).label("weighted_sum"),
            func.sum(ResponseHourlyStats.response_count).label("response_count"),
        )
        .where(ResponseHourlyStats.analysis_date >= start_date, ResponseHourlyStats.analysis_date <= end_date)
        .group_by(ResponseHourlyStats.analysis_date, ResponseHourlyStats.hour)
        .order_by(ResponseHourlyStats.analysis_date, ResponseHourlyStats.hour)
    )
    if conversation_type != "all":
        stmt = stmt.where(ResponseHourlyStats.conversation_type == conversation_type)
    rows = []
    for row in analysis_db.execute(stmt).all():
        count = int(row.response_count or 0)
        avg = int((row.weighted_sum or 0) / count) if count else 0
        rows.append(
            {
                "analysis_date": row.analysis_date.isoformat(),
                "hour": int(row.hour),
                "response_avg_seconds": avg,
                "response_count": count,
            }
        )
    base = _meta("analysis", len(rows), request_id=request_id, sql=sql, chart_hint="line")
    return _response(request_id, sql, rows, base["meta"])


@router.get("/questions", dependencies=[Depends(require_chatbi_token)])
def questions(
    start_date: date,
    end_date: date,
    request_id: str = "chatbi_questions",
    limit: int = Query(default=100, ge=1, le=ARCHIVE_MAX_LIMIT),
    analysis_db: Session = Depends(get_analysis_db),
    archive_db: Session = Depends(get_db),
) -> dict:
    labels = _labels()
    sql = (
        "select * from analysis_question_detail where is_question = true "
        "and question_category != 'uncategorized' and analysis_date between :start_date and :end_date"
    )
    stmt = (
        select(QuestionDetail)
        .where(
            QuestionDetail.analysis_date >= start_date,
            QuestionDetail.analysis_date <= end_date,
            QuestionDetail.is_question.is_(True),
            QuestionDetail.question_category != QUESTION_EXCLUDED,
        )
        .order_by(QuestionDetail.analysis_date.desc(), QuestionDetail.id.desc())
        .limit(limit)
    )
    msgids = []
    details = list(analysis_db.scalars(stmt).all())
    for item in details:
        msgids.append(item.msgid)
    message_times = {}
    if msgids:
        for msgid, msg_time in archive_db.execute(select(Message.msgid, Message.msg_time).where(Message.msgid.in_(msgids))):
            message_times[msgid] = msg_time
    rows = [
        {
            "analysis_date": item.analysis_date.isoformat(),
            "roomid": item.roomid,
            "room_name": item.room_name,
            "msgid": item.msgid,
            "content_text": item.content_text,
            "question_category": item.question_category,
            "question_category_name": labels.get(item.question_category, item.question_category),
            "sender_display_name": item.sender_group_remark or item.sender_wechat_name or item.sender_external_userid,
            "msg_time": _utc_naive_to_beijing(message_times[item.msgid]) if item.msgid in message_times else None,
        }
        for item in details
    ]
    base = _meta("analysis", len(rows), request_id=request_id, sql=sql, chart_hint="bar", limit=limit)
    return _response(request_id, sql, rows, base["meta"])


@router.get("/sentiment", dependencies=[Depends(require_chatbi_token)])
def sentiment(
    start_date: date,
    end_date: date,
    request_id: str = "chatbi_sentiment",
    analysis_db: Session = Depends(get_analysis_db),
) -> dict:
    sql = "select sentiment counts from analysis_sentiment_daily_stats where analysis_date between :start_date and :end_date"
    stmt = select(SentimentDailyStats).where(
        SentimentDailyStats.analysis_date >= start_date,
        SentimentDailyStats.analysis_date <= end_date,
    )
    counts = Counter()
    for row in analysis_db.scalars(stmt):
        counts["positive_count"] += row.positive_count
        counts["neutral_count"] += row.neutral_count
        counts["negative_count"] += row.negative_count
        counts["total_count"] += row.total_count
    rows = [dict(counts)]
    base = _meta("analysis", len(rows), request_id=request_id, sql=sql, chart_hint="donut")
    return _response(request_id, sql, rows, base["meta"])


@router.get("/hotwords", dependencies=[Depends(require_chatbi_token)])
def hotwords(
    start_date: date,
    end_date: date,
    request_id: str = "chatbi_hotwords",
    top_n: int = Query(default=20, ge=1, le=100),
    analysis_db: Session = Depends(get_analysis_db),
) -> dict:
    sql = "select hotwords from analysis_hotword_daily_stats where analysis_date between :start_date and :end_date"
    counter = Counter()
    stmt = select(HotwordDailyStats).where(
        HotwordDailyStats.analysis_date >= start_date,
        HotwordDailyStats.analysis_date <= end_date,
    )
    for row in analysis_db.scalars(stmt):
        for item in row.hotwords or []:
            counter[str(item.get("word", ""))] += int(item.get("count", 0) or 0)
    rows = [{"word": word, "count": count} for word, count in counter.most_common(top_n) if word]
    base = _meta("analysis", len(rows), request_id=request_id, sql=sql, chart_hint="bar", limit=top_n)
    return _response(request_id, sql, rows, base["meta"])


@router.get("/archive-search", dependencies=[Depends(require_chatbi_token)])
def archive_search(
    keyword: str,
    start_datetime: datetime,
    end_datetime: datetime,
    request_id: str = "chatbi_archive_search",
    conversation_type: Literal["all", "single", "room"] = "all",
    limit: int = Query(default=100, ge=1),
    archive_db: Session = Depends(get_db),
) -> dict:
    safe_limit = _archive_limit(limit)
    start_utc = _beijing_naive_to_utc_naive(start_datetime)
    end_utc = _beijing_naive_to_utc_naive(end_datetime)
    sql = (
        "select msgid, conversation_type, roomid, sender_id, sender_type, sender_name, content_text, msg_time "
        "from message where content_text like :keyword and msg_time >= :start_utc and msg_time < :end_utc"
    )
    stmt = (
        select(Message)
        .where(
            Message.content_text.contains(keyword),
            Message.msg_time >= start_utc,
            Message.msg_time < end_utc,
            Message.is_recalled.is_(False),
        )
        .order_by(Message.msg_time.desc(), Message.id.desc())
        .limit(safe_limit)
    )
    if conversation_type != "all":
        stmt = stmt.where(Message.conversation_type == conversation_type)
        sql += " and conversation_type = :conversation_type"
    sql += " order by msg_time desc limit :limit"
    rows = [
        {
            "msgid": item.msgid,
            "conversation_type": item.conversation_type,
            "roomid": item.roomid,
            "sender_id": item.sender_id,
            "sender_type": item.sender_type,
            "sender_name": item.sender_name,
            "content_text": item.content_text,
            "msg_time": _utc_naive_to_beijing(item.msg_time),
        }
        for item in archive_db.scalars(stmt).all()
    ]
    meta = _meta(
        "archive",
        len(rows),
        request_id=request_id,
        sql=sql,
        limit=safe_limit,
        truncated=len(rows) >= safe_limit,
        fallback_used=True,
    )["meta"]
    meta["time_zone"] = "Asia/Shanghai"
    return _response(request_id, sql, rows, meta)
