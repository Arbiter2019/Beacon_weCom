from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import delete

from analysis_app.config import load_settings
from analysis_app.db import create_session_makers, initialize_analysis_schema
from analysis_app.models import (
    ConversationSnapshot,
    HotwordDailyStats,
    MessageDailyStats,
    QuestionDetail,
    ResponseHourlyStats,
    SentimentDailyStats,
    SentimentDetail,
)


def _date_range(start_date: date, end_date: date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def rollback_analysis(
    start_date: date,
    end_date: date,
    observer_userid: str | None = None,
    tasks: list[str] | None = None,
) -> dict:
    settings = load_settings()
    _, analysis_engine, _, analysis_session_maker = create_session_makers(settings)
    initialize_analysis_schema(analysis_engine)
    selected_tasks = tasks or ["snapshot", "basic", "response", "sentiment", "hotwords", "question"]
    deleted = []

    with analysis_session_maker() as analysis_db:
        for day in _date_range(start_date, end_date):
            for task in selected_tasks:
                if task == "snapshot":
                    stmt = delete(ConversationSnapshot).where(ConversationSnapshot.analysis_date == day)
                    if observer_userid is not None:
                        stmt = stmt.where(ConversationSnapshot.observer_userid == observer_userid)
                elif task == "basic":
                    stmt = delete(MessageDailyStats).where(MessageDailyStats.analysis_date == day)
                    if observer_userid is not None:
                        stmt = stmt.where(MessageDailyStats.observer_userid == observer_userid)
                elif task == "response":
                    stmt = delete(ResponseHourlyStats).where(ResponseHourlyStats.analysis_date == day)
                    if observer_userid is not None:
                        stmt = stmt.where(ResponseHourlyStats.observer_userid == observer_userid)
                elif task == "sentiment":
                    detail_stmt = delete(SentimentDetail).where(SentimentDetail.analysis_date == day)
                    if observer_userid is not None:
                        detail_stmt = detail_stmt.where(SentimentDetail.observer_userid == observer_userid)
                    detail_result = analysis_db.execute(detail_stmt)
                    deleted.append({"task": task, "date": day.isoformat(), "rows": detail_result.rowcount or 0})
                    stmt = delete(SentimentDailyStats).where(SentimentDailyStats.analysis_date == day)
                    if observer_userid is not None:
                        stmt = stmt.where(SentimentDailyStats.observer_userid == observer_userid)
                elif task == "hotwords":
                    stmt = delete(HotwordDailyStats).where(HotwordDailyStats.analysis_date == day)
                    if observer_userid is not None:
                        stmt = stmt.where(HotwordDailyStats.observer_userid == observer_userid)
                elif task == "question":
                    stmt = delete(QuestionDetail).where(QuestionDetail.analysis_date == day)
                    if observer_userid is not None:
                        stmt = stmt.where(QuestionDetail.observer_userid == observer_userid)
                else:
                    raise ValueError(f"unsupported task: {task}")
                result = analysis_db.execute(stmt)
                deleted.append({"task": task, "date": day.isoformat(), "rows": result.rowcount or 0})
        analysis_db.commit()

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "observer_userid": observer_userid,
        "tasks": selected_tasks,
        "deleted": deleted,
    }
