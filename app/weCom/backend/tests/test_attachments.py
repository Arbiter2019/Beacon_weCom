from datetime import datetime

from wecom_app.models import Attachment, Message, RawMessage
from wecom_app.services.attachments import backfill_image_attachments, download_pending_attachments


def test_download_pending_attachments_saves_image_to_local_storage(db, tmp_path):
    message = db.query(Message).filter_by(msgid="msg_text_1").one()
    attachment = Attachment(
        message_id=message.id,
        msgid="msg_image_1",
        attachment_type="image",
        sdkfileid="sdk-image",
        md5sum="abc123",
        file_size=7,
    )
    db.add(attachment)
    db.commit()

    class FakeArchiveClient:
        def download_media(self, sdkfileid):
            assert sdkfileid == "sdk-image"
            return b"imgdata"

    result = download_pending_attachments(db, FakeArchiveClient(), tmp_path, limit=10)

    db.refresh(attachment)
    assert result == {"processed": 1, "downloaded": 1, "failed": 0}
    assert attachment.download_status == "downloaded"
    assert attachment.storage_backend == "local_volume"
    assert attachment.storage_key == f"2026/06/19/{attachment.id}_abc123.image"
    assert (tmp_path / attachment.storage_key).read_bytes() == b"imgdata"


def test_download_pending_attachments_marks_failures(db, tmp_path):
    message = db.query(Message).filter_by(msgid="msg_text_1").one()
    attachment = Attachment(
        message_id=message.id,
        msgid="msg_image_2",
        attachment_type="image",
        sdkfileid="sdk-broken",
    )
    db.add(attachment)
    db.commit()

    class FakeArchiveClient:
        def download_media(self, sdkfileid):
            raise RuntimeError("sdk failed")

    result = download_pending_attachments(db, FakeArchiveClient(), tmp_path, limit=10)

    db.refresh(attachment)
    assert result == {"processed": 1, "downloaded": 0, "failed": 1}
    assert attachment.download_status == "failed"
    assert attachment.download_error == "sdk failed"


def test_backfill_image_attachments_creates_missing_rows_for_existing_messages(db):
    raw = RawMessage(
        seq=40,
        msgid="msg_history_image_raw",
        decrypt_payload={"msgtype": "image"},
        process_status="processed",
        msg_time=datetime(2026, 6, 19, 9, 40),
    )
    db.add(raw)
    db.flush()
    message = Message(
        raw_message_id=raw.id,
        seq=40,
        msgid="msg_history_image",
        action="send",
        msg_type="image",
        conversation_type="single",
        sender_id="wang_teacher",
        sender_type="employee",
        content_text="[图片]",
        msg_time_ms=1781833200000,
        msg_time=datetime(2026, 6, 19, 9, 40),
        raw_payload={"msgtype": "image", "image": {"sdkfileid": "sdk-history", "md5sum": "old-md5"}},
    )
    db.add(message)
    db.commit()

    result = backfill_image_attachments(db)

    attachment = db.query(Attachment).filter_by(msgid="msg_history_image").one()
    assert result == {"processed": 1, "created": 1}
    assert attachment.sdkfileid == "sdk-history"
    assert attachment.md5sum == "old-md5"
