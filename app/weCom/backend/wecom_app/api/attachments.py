from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from wecom_app.core.config import Settings, get_settings
from wecom_app.db.session import SessionLocal, get_db
from wecom_app.models import Attachment
from wecom_app.services.attachments import attachment_download_payload, claim_attachment_download
from wecom_app.services.attachments import run_attachment_download_task
from wecom_app.services.storage import get_attachment_storage
from wecom_app.wecom.client import WeComArchiveClient

router = APIRouter(prefix="/api/attachments")


def _run_attachment_download_background(attachment_id: int) -> None:
    with SessionLocal() as db:
        try:
            settings = get_settings()
            storage = get_attachment_storage(settings)
            run_attachment_download_task(db, attachment_id, WeComArchiveClient, storage)
        except Exception as exc:
            attachment = db.get(Attachment, attachment_id)
            if attachment is None:
                return
            attachment.download_status = "failed"
            attachment.download_error = str(exc)
            db.commit()


def require_attachment_token(
    authorization: str | None = Header(default=None),
    token: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> str:
    expected = settings.internal_admin_token
    if authorization == f"Bearer {expected}" or token == expected:
        return "internal_admin"
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin token")


@router.get("/{attachment_id}/content")
def attachment_content(
    attachment_id: int,
    _: str = Depends(require_attachment_token),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    attachment = db.scalar(select(Attachment).where(Attachment.id == attachment_id))
    if attachment is None:
        raise HTTPException(status_code=404, detail="attachment not found")
    if attachment.download_status != "downloaded" or not attachment.storage_key:
        raise HTTPException(status_code=409, detail="attachment not downloaded")
    if attachment.storage_backend != "aliyun_oss":
        raise HTTPException(status_code=409, detail="attachment is not stored in aliyun oss")
    storage = get_attachment_storage(settings)
    stored = storage.open_object(attachment.storage_key)
    headers = {}
    if attachment.file_name:
        headers["Content-Disposition"] = f'inline; filename="{attachment.file_name}"'
    if stored.content_length is not None:
        headers["Content-Length"] = str(stored.content_length)
    return StreamingResponse(stored.chunks, media_type=stored.content_type, headers=headers)


@router.post("/{attachment_id}/download")
def download_attachment(
    attachment_id: int,
    background_tasks: BackgroundTasks,
    _: str = Depends(require_attachment_token),
    db: Session = Depends(get_db),
) -> JSONResponse:
    result = claim_attachment_download(db, attachment_id)
    if not result["found"]:
        raise HTTPException(status_code=404, detail="attachment not found")
    if result["claimed"]:
        background_tasks.add_task(_run_attachment_download_background, attachment_id)
    status_code = status.HTTP_200_OK if result["download_status"] == "downloaded" else status.HTTP_202_ACCEPTED
    attachment = db.get(Attachment, attachment_id)
    payload = attachment_download_payload(attachment) if attachment is not None else result
    return JSONResponse(status_code=status_code, content=payload)
