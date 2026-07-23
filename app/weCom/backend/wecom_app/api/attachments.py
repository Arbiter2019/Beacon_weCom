from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from wecom_app.core.config import Settings, get_settings
from wecom_app.db.session import get_db
from wecom_app.models import Attachment

router = APIRouter(prefix="/api/attachments")


def _sniff_media_type(path: Path, attachment: Attachment) -> str | None:
    header = path.read_bytes()[:12]
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    if attachment.attachment_type == "image":
        return "image/jpeg"
    return None


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
    return FileResponse(Path(path), filename=attachment.file_name, media_type=_sniff_media_type(path, attachment))
