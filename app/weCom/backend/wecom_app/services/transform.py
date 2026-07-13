from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from wecom_app.models import Attachment, Message, MessageRecipient, RawMessage

SUPPORTED_TYPES = {"text", "image", "link", "agree", "disagree"}


def ms_to_datetime(value: int | None) -> datetime:
    if value is None:
        return datetime.utcnow()
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).replace(tzinfo=None)


def sender_type(sender_id: str) -> str:
    if sender_id.startswith("external_") or sender_id.startswith("wm"):
        return "external_contact"
    return "employee"


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


def transform_pending_messages(db: Session, limit: int = 100) -> int:
    raws = db.scalars(
        select(RawMessage).where(RawMessage.process_status == "pending").order_by(RawMessage.seq).limit(limit)
    ).all()
    for raw in raws:
        transform_raw_message(db, raw)
    db.commit()
    return len(raws)
