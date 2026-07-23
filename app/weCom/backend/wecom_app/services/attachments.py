from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from wecom_app.models import Attachment, Message


BROKEN_CLIENT_ERRORS = ("Broken pipe", "SDK worker process terminated unexpectedly")
EXPIRED_MEDIA_ERROR = "GetMediaData error code=10010"


def attachment_path(root: Path, attachment: Attachment) -> Path | None:
    if not attachment.storage_key:
        return None
    return (root / attachment.storage_key).resolve()


def _storage_key(attachment: Attachment) -> str:
    date_part = attachment.message.msg_time.strftime("%Y/%m/%d")
    suffix = attachment.file_ext or attachment.attachment_type
    identity = attachment.md5sum or attachment.msgid
    return f"{date_part}/{attachment.id}_{identity}.{suffix}"


def backfill_image_attachments(db: Session, limit: int = 200) -> dict:
    attached_message_ids = set(db.scalars(select(Attachment.message_id)).all())
    rows = db.scalars(
        select(Message)
        .where(Message.msg_type == "image")
        .order_by(Message.msg_time.asc(), Message.id.asc())
        .limit(limit)
    ).all()
    created = 0
    for message in rows:
        if message.id in attached_message_ids:
            continue
        image = message.raw_payload.get("image") if message.raw_payload else None
        db.add(
            Attachment(
                message_id=message.id,
                msgid=message.msgid,
                attachment_type="image",
                sdkfileid=(image or {}).get("sdkfileid"),
                md5sum=(image or {}).get("md5sum"),
                file_size=(image or {}).get("filesize"),
                raw_payload=image or {},
            )
        )
        created += 1
    db.commit()
    return {"processed": len(rows), "created": created}


def _is_broken_client_error(exc: Exception) -> bool:
    return isinstance(exc, BrokenPipeError) or any(marker in str(exc) for marker in BROKEN_CLIENT_ERRORS)


def _close_client(client) -> None:
    close = getattr(client, "close", None)
    if close is None:
        return
    try:
        close()
    except Exception:
        pass


def _is_expired_media_error(exc: Exception) -> bool:
    return EXPIRED_MEDIA_ERROR in str(exc)


def download_pending_attachments(db: Session, client, root: Path, limit: int = 20, client_factory=None) -> dict:
    attachments = db.scalars(
        select(Attachment)
        .where(
            Attachment.download_status.in_(["pending", "failed"]),
            Attachment.sdkfileid.is_not(None),
        )
        .order_by(Attachment.created_at.desc(), Attachment.id.desc())
        .limit(limit)
    ).all()
    downloaded = 0
    failed = 0
    for attachment in attachments:
        active_client = client
        if client_factory is not None and active_client is None:
            active_client = client_factory()
        try:
            try:
                data = active_client.download_media(attachment.sdkfileid)
            except Exception as exc:
                if client_factory is None or not _is_broken_client_error(exc):
                    raise
                _close_client(active_client)
                active_client = client_factory()
                data = active_client.download_media(attachment.sdkfileid)
            storage_key = _storage_key(attachment)
            path = root / storage_key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            attachment.storage_backend = "local_volume"
            attachment.storage_key = storage_key
            attachment.download_status = "downloaded"
            attachment.download_error = None
            attachment.downloaded_at = datetime.utcnow()
            downloaded += 1
        except Exception as exc:
            attachment.download_status = "expired" if _is_expired_media_error(exc) else "failed"
            attachment.download_error = str(exc)
            failed += 1
        finally:
            if client_factory is not None:
                _close_client(active_client)
                client = None
    db.commit()
    return {"processed": len(attachments), "downloaded": downloaded, "failed": failed}
