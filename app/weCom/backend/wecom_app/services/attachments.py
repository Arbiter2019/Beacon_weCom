from pathlib import Path

from wecom_app.models import Attachment


def attachment_path(root: Path, attachment: Attachment) -> Path | None:
    if not attachment.storage_key:
        return None
    return (root / attachment.storage_key).resolve()
