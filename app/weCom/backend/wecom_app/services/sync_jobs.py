from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from wecom_app.models import SyncCursor
from wecom_app.services.transform import transform_pending_messages
from wecom_app.wecom.client import SyncResult, WeComArchiveClient


def sync_messages_once(db: Session, client: WeComArchiveClient | None = None) -> SyncResult:
    client = client or WeComArchiveClient()
    cursor = db.scalar(select(SyncCursor).where(SyncCursor.cursor_type == "message_seq"))
    if cursor is None:
        cursor = SyncCursor(cursor_type="message_seq", cursor_value="0")
        db.add(cursor)
        db.flush()
    seq = int(cursor.cursor_value or "0")
    fetched_messages = client.get_chat_data(seq)
    cursor.last_run_at = datetime.utcnow()
    cursor.last_success_at = datetime.utcnow()
    if fetched_messages:
        cursor.cursor_value = str(max(int(item["seq"]) for item in fetched_messages))
    processed = transform_pending_messages(db)
    db.commit()
    return SyncResult(fetched=len(fetched_messages), processed=processed, message="message sync completed")
