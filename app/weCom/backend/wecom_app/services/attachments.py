from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from wecom_app.models import Attachment, Message
from wecom_app.services.storage import attachment_content_type, build_attachment_storage_key


BROKEN_CLIENT_ERRORS = ("Broken pipe", "SDK worker process terminated unexpectedly")
EXPIRED_MEDIA_ERROR = "GetMediaData error code=10010"


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


def attachment_download_payload(attachment: Attachment) -> dict:
    return {
        "attachment_id": attachment.id,
        "type": attachment.attachment_type,
        "download_status": attachment.download_status,
        "url": (
            f"/api/attachments/{attachment.id}/content"
            if attachment.download_status == "downloaded"
            else None
        ),
        "download_error": attachment.download_error,
    }


def claim_attachment_download(db: Session, attachment_id: int) -> dict:
    attachment = db.get(Attachment, attachment_id)
    if attachment is None:
        return {"found": False, "claimed": False, "download_status": None}
    if attachment.download_status == "downloaded":
        return {"found": True, "claimed": False, **attachment_download_payload(attachment)}
    if attachment.download_status == "downloading":
        return {"found": True, "claimed": False, **attachment_download_payload(attachment)}
    if attachment.download_status not in {"pending", "failed"}:
        return {"found": True, "claimed": False, **attachment_download_payload(attachment)}

    result = db.execute(
        update(Attachment)
        .where(
            Attachment.id == attachment_id,
            Attachment.download_status.in_(["pending", "failed"]),
        )
        .values(download_status="downloading", download_error=None)
    )
    db.commit()
    db.refresh(attachment)
    return {
        "found": True,
        "claimed": result.rowcount == 1,
        **attachment_download_payload(attachment),
    }


def _download_with_retry(client, sdkfileid: str, client_factory=None) -> bytes:
    active_client = client
    if client_factory is not None and active_client is None:
        active_client = client_factory()
    try:
        try:
            return active_client.download_media(sdkfileid)
        except Exception as exc:
            if client_factory is None or not _is_broken_client_error(exc):
                raise
            _close_client(active_client)
            active_client = client_factory()
            return active_client.download_media(sdkfileid)
    finally:
        if client_factory is not None:
            _close_client(active_client)


def run_attachment_download_task(db: Session, attachment_id: int, client_factory, storage) -> dict:
    attachment = db.get(Attachment, attachment_id)
    if attachment is None:
        return {"found": False, "download_status": None}
    if attachment.download_status == "downloaded":
        return {"found": True, **attachment_download_payload(attachment)}
    if not attachment.sdkfileid:
        attachment.download_status = "failed"
        attachment.download_error = "attachment sdkfileid missing"
        db.commit()
        return {"found": True, **attachment_download_payload(attachment)}

    try:
        data = _download_with_retry(None, attachment.sdkfileid, client_factory=client_factory)
        storage_key = build_attachment_storage_key(attachment, storage.prefix)
        content_type = attachment_content_type(attachment, storage_key)
        storage.put_bytes(storage_key, data, content_type=content_type)
        attachment.storage_backend = storage.backend
        attachment.storage_bucket = storage.bucket
        attachment.storage_key = storage_key
        attachment.storage_url = None
        attachment.download_status = "downloaded"
        attachment.download_error = None
        attachment.downloaded_at = datetime.utcnow()
    except Exception as exc:
        attachment.download_status = "expired" if _is_expired_media_error(exc) else "failed"
        attachment.download_error = str(exc)
    db.commit()
    db.refresh(attachment)
    return {"found": True, **attachment_download_payload(attachment)}


def download_pending_attachments(db: Session, client_factory, storage, limit: int = 100) -> dict:
    attachment_ids = list(
        db.scalars(
            select(Attachment.id)
            .where(Attachment.download_status.in_(["pending", "failed"]))
            .order_by(Attachment.created_at.asc(), Attachment.id.asc())
            .limit(limit)
        )
    )
    result = {"processed": 0, "downloaded": 0, "failed": 0, "expired": 0, "skipped": 0}
    for attachment_id in attachment_ids:
        claim = claim_attachment_download(db, attachment_id)
        if not claim.get("claimed"):
            result["skipped"] += 1
            continue
        download = run_attachment_download_task(db, attachment_id, client_factory, storage)
        result["processed"] += 1
        status = download.get("download_status")
        if status == "downloaded":
            result["downloaded"] += 1
        elif status == "expired":
            result["expired"] += 1
        elif status == "failed":
            result["failed"] += 1
    return result
