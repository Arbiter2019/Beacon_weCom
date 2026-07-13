from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from wecom_app.api.deps import require_admin
from wecom_app.core.config import Settings, get_settings
from wecom_app.db.session import get_db
from wecom_app.models import Attachment

router = APIRouter(prefix="/api/attachments", dependencies=[Depends(require_admin)])


@router.get("/{attachment_id}/content")
def attachment_content(
    attachment_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    attachment = db.scalar(select(Attachment).where(Attachment.id == attachment_id))
    if attachment is None:
        raise HTTPException(status_code=404, detail="attachment not found")
    if attachment.download_status != "downloaded" or not attachment.storage_key:
        raise HTTPException(status_code=409, detail="attachment not downloaded")
    path = (settings.attachment_storage_root / attachment.storage_key).resolve()
    root = settings.attachment_storage_root.resolve()
    if root not in path.parents and path != root:
        raise HTTPException(status_code=403, detail="invalid storage key")
    if not path.exists():
        raise HTTPException(status_code=404, detail="attachment file missing")
    return FileResponse(Path(path), filename=attachment.file_name)
