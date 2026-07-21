from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from wecom_app.models import (
    Attachment,
    CustomerChat,
    CustomerChatMember,
    EmployeeExternalContact,
    ExternalContact,
    Message,
    MessageRecipient,
    RawMessage,
)

SUPPORTED_TYPES = {"text", "image", "link", "agree", "disagree"}


def ms_to_datetime(value: int | None) -> datetime:
    if value is None:
        return datetime.utcnow()
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).replace(tzinfo=None)


def sender_type(sender_id: str) -> str:
    if sender_id.startswith("external_") or sender_id.startswith("wm"):
        return "external_contact"
    return "employee"


def ensure_room_conversation(db: Session, roomid: str, from_user: str, tolist: list[str]) -> None:
    chat = db.scalar(select(CustomerChat).where(CustomerChat.chat_id == roomid))
    if chat is None:
        chat = CustomerChat(
            chat_id=roomid,
            name=roomid,
            owner_userid=from_user if sender_type(from_user) == "employee" else None,
            member_count=len({from_user, *tolist}),
            status="active",
            raw_payload={"source": "message_fallback"},
        )
        db.add(chat)
    for userid in {from_user, *tolist}:
        if sender_type(userid) != "employee":
            continue
        member = db.scalar(
            select(CustomerChatMember).where(
                CustomerChatMember.chat_id == roomid,
                CustomerChatMember.member_userid == userid,
            )
        )
        if member is None:
            db.add(
                CustomerChatMember(
                    chat_id=roomid,
                    member_userid=userid,
                    member_type="employee",
                    role="owner" if userid == chat.owner_userid else "member",
                    is_active=True,
                    raw_payload={"source": "message_fallback"},
                )
            )


def ensure_single_conversations(db: Session, from_user: str, tolist: list[str]) -> None:
    participants = [from_user, *tolist]
    employees = [userid for userid in participants if sender_type(userid) == "employee"]
    externals = [userid for userid in participants if sender_type(userid) == "external_contact"]
    for external_userid in externals:
        pending_contact = any(
            isinstance(obj, ExternalContact) and obj.external_userid == external_userid
            for obj in db.new
        )
        if pending_contact:
            continue
        contact = db.scalar(select(ExternalContact).where(ExternalContact.external_userid == external_userid))
        if contact is None:
            db.add(
                ExternalContact(
                    external_userid=external_userid,
                    name=external_userid,
                    raw_payload={"source": "message_fallback"},
                )
            )
    for employee_userid in employees:
        for external_userid in externals:
            pending_rel = any(
                isinstance(obj, EmployeeExternalContact)
                and obj.userid == employee_userid
                and obj.external_userid == external_userid
                for obj in db.new
            )
            if pending_rel:
                continue
            rel = db.scalar(
                select(EmployeeExternalContact).where(
                    EmployeeExternalContact.userid == employee_userid,
                    EmployeeExternalContact.external_userid == external_userid,
                )
            )
            if rel is None:
                db.add(
                    EmployeeExternalContact(
                        userid=employee_userid,
                        external_userid=external_userid,
                        raw_payload={"source": "message_fallback"},
                    )
                )


def transform_raw_message(db: Session, raw: RawMessage) -> str:
    payload = raw.decrypt_payload or {}
    action = payload.get("action") or raw.msg_action or "send"
    msg_type = payload.get("msgtype") or raw.msg_type or "unknown"
    if action == "recall" or msg_type in {"revoke", "recall"}:
        pre_msgid = (payload.get("revoke") or {}).get("pre_msgid")
        if pre_msgid:
            original = db.scalar(select(Message).where(Message.msgid == pre_msgid))
            if original:
                original.is_recalled = True
                original.recalled_at = ms_to_datetime(payload.get("msgtime") or raw.msg_time_ms)
                original.recall_raw_message_id = raw.id
        raw.process_status = "processed"
        raw.processed_at = datetime.utcnow()
        return "recall"

    existing = db.scalar(select(Message).where(Message.msgid == raw.msgid))
    if existing:
        raw.process_status = "processed"
        raw.processed_at = datetime.utcnow()
        return "duplicate"

    from_user = payload.get("from") or payload.get("sender") or "unknown"
    tolist = payload.get("tolist") or []
    roomid = payload.get("roomid")
    if roomid:
        ensure_room_conversation(db, roomid, from_user, tolist)
    else:
        ensure_single_conversations(db, from_user, tolist)
    is_supported = msg_type in SUPPORTED_TYPES
    text = None
    link_title = link_url = link_description = None
    if msg_type == "text":
        text = (payload.get("text") or {}).get("content")
    elif msg_type == "link":
        link = payload.get("link") or {}
        link_title = link.get("title")
        link_url = link.get("link_url") or link.get("url")
        link_description = link.get("description")
        text = link_title or link_url
    elif msg_type in {"agree", "disagree"}:
        text = "同意会话存档" if msg_type == "agree" else "不同意会话存档"
    elif msg_type == "image":
        text = "[图片]"
    else:
        text = f"暂不支持的 {msg_type} 消息"

    message = Message(
        raw_message_id=raw.id,
        seq=raw.seq,
        msgid=raw.msgid,
        action=action,
        msg_type=msg_type,
        conversation_type="room" if roomid else "single",
        roomid=roomid,
        sender_id=from_user,
        sender_type=sender_type(from_user),
        sender_name=payload.get("sender_name"),
        content_text=text,
        link_title=link_title,
        link_url=link_url,
        link_description=link_description,
        msg_time_ms=payload.get("msgtime") or raw.msg_time_ms or 0,
        msg_time=ms_to_datetime(payload.get("msgtime") or raw.msg_time_ms),
        is_external=sender_type(from_user) == "external_contact",
        is_supported=is_supported,
        raw_payload=payload,
    )
    db.add(message)
    db.flush()
    for recipient in tolist:
        db.add(
            MessageRecipient(
                message_id=message.id,
                msgid=message.msgid,
                recipient_id=recipient,
                recipient_type=sender_type(recipient),
            )
        )
    if msg_type == "image":
        image = payload.get("image") or {}
        db.add(
            Attachment(
                message_id=message.id,
                msgid=message.msgid,
                attachment_type="image",
                sdkfileid=image.get("sdkfileid"),
                md5sum=image.get("md5sum"),
                file_size=image.get("filesize"),
                raw_payload=image,
            )
        )
    raw.process_status = "processed" if is_supported else "ignored"
    raw.processed_at = datetime.utcnow()
    return "message"


def transform_pending_messages(db: Session, limit: int = 100, newest_first: bool = False) -> int:
    stmt = select(RawMessage).where(RawMessage.process_status == "pending")
    if newest_first:
        stmt = stmt.order_by(RawMessage.msg_time.desc(), RawMessage.seq.desc())
    else:
        stmt = stmt.order_by(RawMessage.seq)
    raws = db.scalars(stmt.limit(limit)).all()
    for raw in raws:
        transform_raw_message(db, raw)
    db.commit()
    return len(raws)


def backfill_room_conversations(db: Session, limit: int = 1000) -> int:
    messages = db.scalars(
        select(Message)
        .where(Message.conversation_type == "room", Message.roomid.is_not(None))
        .order_by(Message.msg_time.desc())
        .limit(limit)
    ).all()
    seen: set[str] = set()
    backfilled = 0
    for message in messages:
        if not message.roomid or message.roomid in seen:
            continue
        seen.add(message.roomid)
        existing = db.scalar(select(CustomerChat).where(CustomerChat.chat_id == message.roomid))
        if existing is not None:
            continue
        recipients = [recipient.recipient_id for recipient in message.recipients]
        ensure_room_conversation(db, message.roomid, message.sender_id, recipients)
        backfilled += 1
    db.commit()
    return backfilled


def backfill_single_conversations(db: Session, limit: int = 1000) -> int:
    messages = db.scalars(
        select(Message)
        .where(Message.conversation_type == "single")
        .order_by(Message.msg_time.desc())
        .limit(limit)
    ).all()
    before = db.scalar(select(func.count()).select_from(EmployeeExternalContact)) or 0
    for message in messages:
        recipients = [recipient.recipient_id for recipient in message.recipients]
        ensure_single_conversations(db, message.sender_id, recipients)
    db.commit()
    after = db.scalar(select(func.count()).select_from(EmployeeExternalContact)) or 0
    return max(after - before, 0)
