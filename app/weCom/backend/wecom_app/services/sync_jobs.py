import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from wecom_app.models import RawMessage, SyncCursor
from wecom_app.services.transform import transform_pending_messages
from wecom_app.wecom.client import SyncResult, WeComArchiveClient

logger = logging.getLogger(__name__)


def _save_raw_messages(db: Session, messages: list[dict]) -> int:
    """Upsert decrypted messages into raw_message table."""
    saved = 0
    for payload in messages:
        msgid = payload.get("msgid")
        seq = payload.get("seq")
        if not msgid or not seq:
            continue
        existing = db.scalar(select(RawMessage).where(RawMessage.msgid == msgid))
        if existing:
            continue
        msg_time_ms = payload.get("msgtime")
        raw = RawMessage(
            seq=seq,
            msgid=msgid,
            decrypt_payload=payload,
            msg_action=payload.get("action"),
            msg_type=payload.get("msgtype"),
            msg_time_ms=msg_time_ms,
            msg_time=datetime.utcfromtimestamp(msg_time_ms / 1000) if msg_time_ms else None,
            process_status="pending",
            fetched_at=datetime.utcnow(),
            decrypted_at=datetime.utcnow(),
        )
        db.add(raw)
        saved += 1
    return saved


def sync_messages_once(db: Session, client: WeComArchiveClient | None = None) -> SyncResult:
    if client is None:
        try:
            client = WeComArchiveClient()
        except Exception as exc:
            logger.error("WeComArchiveClient init failed: %s", exc)
            return SyncResult(fetched=0, processed=0, message=f"sdk init error: {exc}")

    cursor = db.scalar(select(SyncCursor).where(SyncCursor.cursor_type == "message_seq"))
    if cursor is None:
        cursor = SyncCursor(cursor_type="message_seq", cursor_value="0")
        db.add(cursor)
        db.flush()
    seq = int(cursor.cursor_value or "0")
    fetched_messages, max_seq = client.get_chat_data(seq)
    cursor.last_run_at = datetime.utcnow()
    cursor.last_success_at = datetime.utcnow()
    # Advance cursor based on max_seq seen (including undecryptable old messages)
    if max_seq > seq:
        cursor.cursor_value = str(max_seq)
    # Persist decrypted messages into raw_message table
    if fetched_messages:
        _save_raw_messages(db, fetched_messages)
        db.flush()  # make new rows visible to transform within the same transaction
    processed = transform_pending_messages(db)
    db.commit()
    return SyncResult(fetched=len(fetched_messages), processed=processed, message="message sync completed")
