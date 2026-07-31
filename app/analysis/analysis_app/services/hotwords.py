from __future__ import annotations

import re
from collections import Counter
from datetime import date

import jieba
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from analysis_app.models import ConversationSnapshot, HotwordDailyStats
from analysis_app.stopwords import load_stopwords
from analysis_app.services.utils import utc_naive_range_for_beijing_day
from wecom_app.models import Message

_TOKEN_RE = re.compile(r"^[\w\u4e00-\u9fff]+$")


def _normalize_tokens(tokens: list[str], stopwords: set[str]) -> list[str]:
    normalized: list[str] = []
    for token in tokens:
        token = token.strip()
        if not token or token in stopwords:
            continue
        if token.isdigit():
            continue
        if len(token) <= 1:
            continue
        if not _TOKEN_RE.match(token):
            continue
        normalized.append(token)
    return normalized


def run_hotwords(
    archive_db: Session,
    analysis_db: Session,
    analysis_date: date,
    observer_userid: str | None = None,
    stopwords_path: str | None = None,
) -> dict:
    snapshot_stmt = select(ConversationSnapshot).where(ConversationSnapshot.analysis_date == analysis_date)
    if observer_userid:
        snapshot_stmt = snapshot_stmt.where(ConversationSnapshot.observer_userid == observer_userid)
    snapshots = list(analysis_db.scalars(snapshot_stmt.where(ConversationSnapshot.conversation_type == "room")).all())
    if not snapshots:
        from analysis_app.services.snapshot import build_daily_snapshot

        snapshots = build_daily_snapshot(archive_db, analysis_db, analysis_date, observer_userid)
        snapshots = [snapshot for snapshot in snapshots if snapshot.conversation_type == "room"]
        analysis_db.expire_all()

    analysis_db.execute(
        delete(HotwordDailyStats).where(
            HotwordDailyStats.analysis_date == analysis_date,
            HotwordDailyStats.observer_userid.in_({snapshot.observer_userid for snapshot in snapshots} or {observer_userid}),
        )
    )
    analysis_db.commit()

    start, end = utc_naive_range_for_beijing_day(analysis_date)
    stopwords = set(load_stopwords(stopwords_path))
    rows: list[HotwordDailyStats] = []
    for snapshot in snapshots:
        stmt = (
            select(Message)
            .where(
                Message.conversation_type == "room",
                Message.roomid == snapshot.roomid,
                Message.is_recalled.is_(False),
                Message.msg_time >= start,
                Message.msg_time < end,
                Message.sender_type == "external_contact",
                Message.msg_type == "text",
            )
            .order_by(Message.msg_time, Message.id)
        )
        tokens: Counter[str] = Counter()
        for message in archive_db.scalars(stmt):
            tokens.update(_normalize_tokens(jieba.lcut(message.content_text or ""), stopwords))
        hotwords = [{"word": word, "count": count} for word, count in tokens.most_common(20)]
        rows.append(
            HotwordDailyStats(
                analysis_date=analysis_date,
                observer_userid=snapshot.observer_userid,
                roomid=snapshot.roomid or "",
                room_name=snapshot.display_name,
                member_count=snapshot.member_count,
                hotwords=hotwords,
            )
        )

    analysis_db.add_all(rows)
    analysis_db.commit()
    return {"rows_written": len(rows), "rows": rows}

