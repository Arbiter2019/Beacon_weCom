from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

PK_TYPE = BigInteger().with_variant(Integer, "sqlite")


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class RawMessage(Base, TimestampMixin):
    __tablename__ = "raw_message"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    seq: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    msgid: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    publickey_ver: Mapped[int | None] = mapped_column(Integer)
    encrypt_random_key: Mapped[str | None] = mapped_column(Text)
    encrypt_chat_msg: Mapped[str | None] = mapped_column(Text)
    decrypt_payload: Mapped[dict | None] = mapped_column(JSON)
    msg_action: Mapped[str | None] = mapped_column(String(32))
    msg_type: Mapped[str | None] = mapped_column(String(64))
    msg_time_ms: Mapped[int | None] = mapped_column(BigInteger)
    msg_time: Mapped[datetime | None] = mapped_column(DateTime)
    process_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    process_error: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    decrypted_at: Mapped[datetime | None] = mapped_column(DateTime)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        Index("ix_raw_message_status_seq", "process_status", "seq"),
        Index("ix_raw_message_msg_time", "msg_time"),
    )


class RawEvent(Base, TimestampMixin):
    __tablename__ = "raw_event"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    event_source: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    event_key: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    external_userid: Mapped[str | None] = mapped_column(String(128))
    chat_id: Mapped[str | None] = mapped_column(String(128))
    userid: Mapped[str | None] = mapped_column(String(128))
    event_time_ms: Mapped[int | None] = mapped_column(BigInteger)
    event_time: Mapped[datetime | None] = mapped_column(DateTime)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    process_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    process_error: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        Index("ix_raw_event_status_received", "process_status", "received_at"),
        Index("ix_raw_event_source_type_time", "event_source", "event_type", "event_time"),
        Index("ix_raw_event_chat", "chat_id"),
        Index("ix_raw_event_external", "external_userid"),
    )


class SyncCursor(Base, TimestampMixin):
    __tablename__ = "sync_cursor"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    cursor_type: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    cursor_value: Mapped[str | None] = mapped_column(String(256))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)


class Department(Base, TimestampMixin):
    __tablename__ = "department"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    department_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    parent_department_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255))
    order_no: Mapped[int | None] = mapped_column(Integer)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raw_payload: Mapped[dict | None] = mapped_column(JSON)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Employee(Base, TimestampMixin):
    __tablename__ = "employee"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    userid: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    alias: Mapped[str | None] = mapped_column(String(255))
    mobile: Mapped[str | None] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(255))
    avatar: Mapped[str | None] = mapped_column(Text)
    position: Mapped[str | None] = mapped_column(String(255))
    department_ids: Mapped[list | None] = mapped_column(JSON)
    main_department_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    status: Mapped[int | None] = mapped_column(Integer, index=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raw_payload: Mapped[dict | None] = mapped_column(JSON)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ObservableEmployeeScope(Base, TimestampMixin):
    __tablename__ = "observable_employee_scope"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    userid: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    scope_status: Mapped[str] = mapped_column(String(32), default="enabled", nullable=False)
    scope_reason: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[str | None] = mapped_column(String(128))
    updated_by: Mapped[str | None] = mapped_column(String(128))

    __table_args__ = (Index("ix_observable_scope_status_userid", "scope_status", "userid"),)


class ConversationViewHistory(Base, TimestampMixin):
    __tablename__ = "conversation_view_history"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    observer_userid: Mapped[str] = mapped_column(String(128), nullable=False)
    conversation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    external_userid: Mapped[str | None] = mapped_column(String(128))
    chat_id: Mapped[str | None] = mapped_column(String(128))
    last_viewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index("ix_conversation_view_observer_time", "observer_userid", "last_viewed_at"),
    )


class ExternalContact(Base, TimestampMixin):
    __tablename__ = "external_contact"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    external_userid: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    avatar: Mapped[str | None] = mapped_column(Text)
    type: Mapped[int | None] = mapped_column(Integer)
    gender: Mapped[int | None] = mapped_column(Integer)
    unionid: Mapped[str | None] = mapped_column(String(128), index=True)
    corp_name: Mapped[str | None] = mapped_column(String(255))
    corp_full_name: Mapped[str | None] = mapped_column(String(255))
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raw_payload: Mapped[dict | None] = mapped_column(JSON)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class EmployeeExternalContact(Base, TimestampMixin):
    __tablename__ = "employee_external_contact"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    userid: Mapped[str] = mapped_column(String(128), nullable=False)
    external_userid: Mapped[str] = mapped_column(String(128), nullable=False)
    remark: Mapped[str | None] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    remark_corp_name: Mapped[str | None] = mapped_column(String(255))
    remark_mobiles: Mapped[list | None] = mapped_column(JSON)
    tag_ids: Mapped[list | None] = mapped_column(JSON)
    add_way: Mapped[int | None] = mapped_column(Integer)
    add_time: Mapped[datetime | None] = mapped_column(DateTime)
    add_time_ms: Mapped[int | None] = mapped_column(BigInteger)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raw_payload: Mapped[dict | None] = mapped_column(JSON)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("userid", "external_userid", name="uq_employee_external_contact"),
        Index("ix_employee_external_external", "external_userid"),
        Index("ix_employee_external_user_deleted", "userid", "is_deleted"),
    )


class CustomerChat(Base, TimestampMixin):
    __tablename__ = "customer_chat"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    chat_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    owner_userid: Mapped[str | None] = mapped_column(String(128), index=True)
    notice: Mapped[str | None] = mapped_column(Text)
    member_count: Mapped[int | None] = mapped_column(Integer)
    admin_userids: Mapped[list | None] = mapped_column(JSON)
    create_time: Mapped[datetime | None] = mapped_column(DateTime)
    create_time_ms: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False, index=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class CustomerChatMember(Base, TimestampMixin):
    __tablename__ = "customer_chat_member"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    chat_id: Mapped[str] = mapped_column(String(128), nullable=False)
    member_userid: Mapped[str] = mapped_column(String(128), nullable=False)
    member_type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    group_nickname: Mapped[str | None] = mapped_column(String(255))
    join_time: Mapped[datetime | None] = mapped_column(DateTime)
    join_time_ms: Mapped[int | None] = mapped_column(BigInteger)
    join_scene: Mapped[int | None] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(32), default="member", nullable=False)
    invitor_userid: Mapped[str | None] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    left_at: Mapped[datetime | None] = mapped_column(DateTime)
    raw_payload: Mapped[dict | None] = mapped_column(JSON)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("chat_id", "member_userid", name="uq_customer_chat_member"),
        Index("ix_customer_chat_member_user_type", "member_userid", "member_type"),
        Index("ix_customer_chat_member_chat_active", "chat_id", "is_active"),
        Index("ix_customer_chat_member_role", "role"),
    )


class Message(Base, TimestampMixin):
    __tablename__ = "message"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    raw_message_id: Mapped[int] = mapped_column(ForeignKey("raw_message.id"), unique=True, nullable=False)
    seq: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    msgid: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    msg_type: Mapped[str] = mapped_column(String(64), nullable=False)
    conversation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    roomid: Mapped[str | None] = mapped_column(String(128))
    sender_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sender_type: Mapped[str] = mapped_column(String(32), nullable=False)
    sender_name: Mapped[str | None] = mapped_column(String(255))
    content_text: Mapped[str | None] = mapped_column(Text)
    link_title: Mapped[str | None] = mapped_column(String(500))
    link_url: Mapped[str | None] = mapped_column(Text)
    link_description: Mapped[str | None] = mapped_column(Text)
    msg_time_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    msg_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_external: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_recalled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recalled_at: Mapped[datetime | None] = mapped_column(DateTime)
    recall_raw_message_id: Mapped[int | None] = mapped_column(BigInteger)
    is_supported: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    recipients: Mapped[list["MessageRecipient"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_message_room_time", "roomid", "msg_time"),
        Index("ix_message_sender_time", "sender_id", "msg_time"),
        Index("ix_message_type_time", "msg_type", "msg_time"),
        Index("ix_message_recalled", "is_recalled"),
    )


class MessageRecipient(Base):
    __tablename__ = "message_recipient"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("message.id"), nullable=False)
    msgid: Mapped[str] = mapped_column(String(128), nullable=False)
    recipient_id: Mapped[str] = mapped_column(String(128), nullable=False)
    recipient_type: Mapped[str] = mapped_column(String(32), nullable=False)
    recipient_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    message: Mapped[Message] = relationship(back_populates="recipients")

    __table_args__ = (
        UniqueConstraint("message_id", "recipient_id", name="uq_message_recipient"),
        Index("ix_message_recipient_id_created", "recipient_id", "created_at"),
    )


class Attachment(Base, TimestampMixin):
    __tablename__ = "attachment"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("message.id"), nullable=False)
    msgid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    attachment_type: Mapped[str] = mapped_column(String(64), nullable=False)
    sdkfileid: Mapped[str | None] = mapped_column(Text)
    md5sum: Mapped[str | None] = mapped_column(String(128), index=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    file_name: Mapped[str | None] = mapped_column(String(500))
    file_ext: Mapped[str | None] = mapped_column(String(64))
    storage_backend: Mapped[str] = mapped_column(String(64), default="aliyun_oss", nullable=False)
    storage_bucket: Mapped[str | None] = mapped_column(String(255))
    storage_key: Mapped[str | None] = mapped_column(Text)
    storage_url: Mapped[str | None] = mapped_column(Text)
    download_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    download_error: Mapped[str | None] = mapped_column(Text)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime)
    raw_payload: Mapped[dict | None] = mapped_column(JSON)

    message: Mapped[Message] = relationship(back_populates="attachments")

    __table_args__ = (
        Index("ix_attachment_status_created", "download_status", "created_at"),
    )
