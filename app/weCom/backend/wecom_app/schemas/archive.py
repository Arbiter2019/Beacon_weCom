from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Page(BaseModel):
    items: list[Any]
    next_cursor: str | None = None


class ObservableEmployeeOut(BaseModel):
    userid: str
    name: str | None = None
    avatar: str | None = None
    department: str | None = None
    scope_status: str
    conversation_count: int = 0


class ObservableEmployeeUpsert(BaseModel):
    userid: str
    scope_status: Literal["enabled", "disabled"] = "enabled"
    scope_reason: str | None = None


class ConversationOut(BaseModel):
    conversation_type: Literal["student", "customer_chat"]
    external_userid: str | None = None
    chat_id: str | None = None
    display_name: str
    wechat_name: str | None = None
    avatar: str | None = None
    summary: str | None = None
    last_message_time: datetime | None = None
    last_viewed_at: datetime | None = None
    sort_basis: Literal["last_viewed", "last_message"] = "last_message"
    member_count: int | None = None
    owner_name: str | None = None
    observer_role: str | None = None


class SenderOut(BaseModel):
    id: str
    type: str
    display_name: str | None = None
    avatar: str | None = None


class MessageContentOut(BaseModel):
    text: str | None = None
    link: dict[str, Any] | None = None
    attachment: dict[str, Any] | None = None


class MessageOut(BaseModel):
    message_id: int
    msgid: str
    msg_type: str
    is_supported: bool
    sender: SenderOut
    content: MessageContentOut
    msg_time: datetime
    is_recalled: bool
    recalled_at: datetime | None = None


class ConversationViewIn(BaseModel):
    conversation_type: Literal["student", "customer_chat"]
    external_userid: str | None = None
    chat_id: str | None = None


class StudentDetailOut(BaseModel):
    external_userid: str
    display_name: str
    wechat_name: str | None = None
    avatar: str | None = None
    remark: str | None = None
    description: str | None = None
    corp_name: str | None = None
    gender: int | None = None
    unionid: str | None = None
    related_userid: str
    add_time: datetime | None = None
    tag_ids: list[str] = Field(default_factory=list)


class CustomerChatDetailOut(BaseModel):
    chat_id: str
    name: str | None = None
    owner_userid: str | None = None
    notice: str | None = None
    member_count: int | None = None
    admin_userids: list[str] = Field(default_factory=list)
    status: str
    members: list[dict[str, Any]] = Field(default_factory=list)


class HealthOut(BaseModel):
    status: str
    app_env: str
    sdk_configured: bool
    private_key_configured: bool
