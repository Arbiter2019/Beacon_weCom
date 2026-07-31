from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, JSON, Date, DateTime, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class ConversationSnapshot(Base, TimestampMixin):
    __tablename__ = "analysis_conversation_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    observer_userid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    conversation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    external_userid: Mapped[str | None] = mapped_column(String(128))
    roomid: Mapped[str | None] = mapped_column(String(128))
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    wechat_name: Mapped[str | None] = mapped_column(String(255))
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    snapshot_payload: Mapped[dict | None] = mapped_column(JSON)

    __table_args__ = (
        UniqueConstraint(
            "analysis_date",
            "observer_userid",
            "conversation_type",
            "external_userid",
            name="uq_analysis_snapshot_external",
        ),
        UniqueConstraint(
            "analysis_date",
            "observer_userid",
            "conversation_type",
            "roomid",
            name="uq_analysis_snapshot_room",
        ),
    )


class MessageDailyStats(Base, TimestampMixin):
    __tablename__ = "analysis_message_daily_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    observer_userid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    conversation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    external_userid: Mapped[str | None] = mapped_column(String(128))
    roomid: Mapped[str | None] = mapped_column(String(128))
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    received_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    received_type_counts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    sent_type_counts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint(
            "analysis_date",
            "observer_userid",
            "conversation_type",
            "external_userid",
            name="uq_analysis_message_external",
        ),
        UniqueConstraint(
            "analysis_date",
            "observer_userid",
            "conversation_type",
            "roomid",
            name="uq_analysis_message_room",
        ),
    )


class ResponseHourlyStats(Base, TimestampMixin):
    __tablename__ = "analysis_response_hourly_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    observer_userid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    conversation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    external_userid: Mapped[str | None] = mapped_column(String(128))
    roomid: Mapped[str | None] = mapped_column(String(128))
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    hour: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    response_avg_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    response_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint(
            "analysis_date",
            "observer_userid",
            "conversation_type",
            "external_userid",
            "roomid",
            "hour",
            name="uq_analysis_response_hour",
        ),
    )


class SentimentDetail(Base, TimestampMixin):
    __tablename__ = "analysis_sentiment_detail"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    observer_userid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    roomid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    room_name: Mapped[str] = mapped_column(String(255), nullable=False)
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    msgid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    sentiment: Mapped[str] = mapped_column(String(32), nullable=False)
    llm_output: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint(
            "analysis_date",
            "observer_userid",
            "roomid",
            "msgid",
            name="uq_analysis_sentiment_msg",
        ),
    )


class SentimentDailyStats(Base, TimestampMixin):
    __tablename__ = "analysis_sentiment_daily_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    observer_userid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    roomid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    room_name: Mapped[str] = mapped_column(String(255), nullable=False)
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    positive_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    neutral_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    negative_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint(
            "analysis_date",
            "observer_userid",
            "roomid",
            name="uq_analysis_sentiment_daily",
        ),
    )


class HotwordDailyStats(Base, TimestampMixin):
    __tablename__ = "analysis_hotword_daily_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    observer_userid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    roomid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    room_name: Mapped[str] = mapped_column(String(255), nullable=False)
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    hotwords: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    __table_args__ = (
        UniqueConstraint(
            "analysis_date",
            "observer_userid",
            "roomid",
            name="uq_analysis_hotword_daily",
        ),
    )


class QuestionDetail(Base, TimestampMixin):
    __tablename__ = "analysis_question_detail"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    observer_userid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    roomid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    room_name: Mapped[str] = mapped_column(String(255), nullable=False)
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    msgid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    sender_external_userid: Mapped[str] = mapped_column(String(128), nullable=False)
    sender_wechat_name: Mapped[str | None] = mapped_column(String(255))
    sender_group_remark: Mapped[str | None] = mapped_column(String(255))
    is_question: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    question_category: Mapped[str] = mapped_column(String(64), nullable=False)
    llm_output: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint(
            "analysis_date",
            "observer_userid",
            "roomid",
            "msgid",
            name="uq_analysis_question_msg",
        ),
    )


class TaskRun(Base, TimestampMixin):
    __tablename__ = "analysis_task_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    analysis_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    observer_userid: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    input_payload: Mapped[dict | None] = mapped_column(JSON)
    result_payload: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
