from datetime import datetime

from wecom_app.models import Attachment, Message, RawMessage
from wecom_app.services.attachments import (
    backfill_image_attachments,
    claim_attachment_download,
    download_pending_attachments,
    run_attachment_download_task,
)


def test_claim_attachment_download_is_idempotent(db):
    message = db.query(Message).filter_by(msgid="msg_text_1").one()
    attachment = Attachment(
        message_id=message.id,
        msgid="msg_image_claim",
        attachment_type="image",
        sdkfileid="sdk-image",
        md5sum="abc123",
    )
    db.add(attachment)
    db.commit()

    first = claim_attachment_download(db, attachment.id)
    second = claim_attachment_download(db, attachment.id)

    db.refresh(attachment)
    assert first["claimed"] is True
    assert first["download_status"] == "downloading"
    assert second["claimed"] is False
    assert second["download_status"] == "downloading"
    assert attachment.download_status == "downloading"


def test_run_attachment_download_task_uploads_to_aliyun_oss(db):
    message = db.query(Message).filter_by(msgid="msg_text_1").one()
    attachment = Attachment(
        message_id=message.id,
        msgid="msg_image_oss",
        attachment_type="image",
        sdkfileid="sdk-image",
        md5sum="abc123",
        file_ext="jpg",
        download_status="downloading",
    )
    db.add(attachment)
    db.commit()

    class FakeArchiveClient:
        def download_media(self, sdkfileid):
            assert sdkfileid == "sdk-image"
            return b"imgdata"

    class FakeStorage:
        backend = "aliyun_oss"
        bucket = "wecom-bucket"
        prefix = "wecom/"

        def __init__(self):
            self.objects = {}

        def put_bytes(self, key, data, content_type=None):
            self.objects[key] = (data, content_type)

    storage = FakeStorage()

    result = run_attachment_download_task(db, attachment.id, lambda: FakeArchiveClient(), storage)

    db.refresh(attachment)
    assert result["download_status"] == "downloaded"
    assert attachment.storage_backend == "aliyun_oss"
    assert attachment.storage_bucket == "wecom-bucket"
    assert attachment.storage_key == f"wecom/image/2026/06/19/{attachment.id}_abc123.jpg"
    assert storage.objects[attachment.storage_key] == (b"imgdata", "image/jpeg")


def test_download_pending_attachments_uploads_pending_rows_to_aliyun_oss(db):
    message = db.query(Message).filter_by(msgid="msg_text_1").one()
    attachment = Attachment(
        message_id=message.id,
        msgid="msg_image_batch_oss",
        attachment_type="image",
        sdkfileid="sdk-image",
        md5sum="batch123",
        file_ext="jpg",
        download_status="pending",
    )
    db.add(attachment)
    db.commit()

    class FakeArchiveClient:
        def download_media(self, sdkfileid):
            assert sdkfileid == "sdk-image"
            return b"batch-img"

    class FakeStorage:
        backend = "aliyun_oss"
        bucket = "wecom-bucket"
        prefix = "wecom/"

        def __init__(self):
            self.objects = {}

        def put_bytes(self, key, data, content_type=None):
            self.objects[key] = (data, content_type)

    storage = FakeStorage()

    result = download_pending_attachments(db, lambda: FakeArchiveClient(), storage)

    db.refresh(attachment)
    assert result == {"processed": 1, "downloaded": 1, "failed": 0, "expired": 0, "skipped": 0}
    assert attachment.download_status == "downloaded"
    assert attachment.storage_backend == "aliyun_oss"
    assert attachment.storage_bucket == "wecom-bucket"
    assert attachment.storage_key in storage.objects


def test_run_attachment_download_task_marks_expired_media(db):
    message = db.query(Message).filter_by(msgid="msg_text_1").one()
    attachment = Attachment(
        message_id=message.id,
        msgid="msg_image_expired_task",
        attachment_type="image",
        sdkfileid="sdk-expired",
        download_status="downloading",
    )
    db.add(attachment)
    db.commit()

    class FakeArchiveClient:
        def download_media(self, sdkfileid):
            raise RuntimeError("GetMediaData error code=10010")

    class FakeStorage:
        backend = "aliyun_oss"
        bucket = "wecom-bucket"
        prefix = "wecom/"

        def put_bytes(self, key, data, content_type=None):
            raise AssertionError("expired media should not be uploaded")

    result = run_attachment_download_task(db, attachment.id, lambda: FakeArchiveClient(), FakeStorage())

    db.refresh(attachment)
    assert result["download_status"] == "expired"
    assert attachment.download_status == "expired"
    assert attachment.download_error == "GetMediaData error code=10010"


def test_attachment_content_accepts_query_token(client, db, monkeypatch):
    from wecom_app.api import attachments as attachment_api

    message = db.query(Message).filter_by(msgid="msg_text_1").one()
    storage_key = "wecom/image/2026/06/19/query-token.image"
    attachment = Attachment(
        message_id=message.id,
        msgid="msg_query_token_image",
        attachment_type="image",
        sdkfileid="sdk-query-token",
        storage_backend="aliyun_oss",
        storage_bucket="wecom-bucket",
        storage_key=storage_key,
        download_status="downloaded",
    )
    db.add(attachment)
    db.commit()

    class FakeStorage:
        def open_object(self, key):
            assert key == storage_key
            from wecom_app.services.storage import StoredObject

            return StoredObject(chunks=iter([b"image-data"]), content_type="image/jpeg")

    monkeypatch.setattr(attachment_api, "get_attachment_storage", lambda settings: FakeStorage())

    response = client.get(f"/api/attachments/{attachment.id}/content?token=dev-admin-token")

    assert response.status_code == 200
    assert response.content == b"image-data"


def test_attachment_download_endpoint_returns_202_after_claim(client, db, auth_headers, monkeypatch):
    from wecom_app.api import attachments as attachment_api

    message = db.query(Message).filter_by(msgid="msg_text_1").one()
    attachment = Attachment(
        message_id=message.id,
        msgid="msg_image_endpoint",
        attachment_type="image",
        sdkfileid="sdk-image",
        download_status="pending",
    )
    db.add(attachment)
    db.commit()
    calls = []

    def fake_background_download(attachment_id):
        calls.append(attachment_id)

    monkeypatch.setattr(attachment_api, "_run_attachment_download_background", fake_background_download)

    response = client.post(f"/api/attachments/{attachment.id}/download", headers=auth_headers)

    assert response.status_code == 202
    assert response.json()["download_status"] == "downloading"
    assert calls == [attachment.id]


def test_attachment_download_endpoint_does_not_duplicate_running_task(
    client, db, auth_headers, monkeypatch
):
    from wecom_app.api import attachments as attachment_api

    message = db.query(Message).filter_by(msgid="msg_text_1").one()
    attachment = Attachment(
        message_id=message.id,
        msgid="msg_image_running",
        attachment_type="image",
        sdkfileid="sdk-image",
        download_status="downloading",
    )
    db.add(attachment)
    db.commit()
    calls = []

    def fake_background_download(attachment_id):
        calls.append(attachment_id)

    monkeypatch.setattr(attachment_api, "_run_attachment_download_background", fake_background_download)

    response = client.post(f"/api/attachments/{attachment.id}/download", headers=auth_headers)

    assert response.status_code == 202
    assert response.json()["download_status"] == "downloading"
    assert calls == []


def test_attachment_content_serves_image_media_type(client, db, monkeypatch):
    from wecom_app.api import attachments as attachment_api

    message = db.query(Message).filter_by(msgid="msg_text_1").one()
    storage_key = "wecom/image/2026/06/19/photo.image"
    attachment = Attachment(
        message_id=message.id,
        msgid="msg_jpeg_image",
        attachment_type="image",
        sdkfileid="sdk-jpeg",
        storage_backend="aliyun_oss",
        storage_bucket="wecom-bucket",
        storage_key=storage_key,
        download_status="downloaded",
    )
    db.add(attachment)
    db.commit()

    class FakeStorage:
        def open_object(self, key):
            assert key == storage_key
            from wecom_app.services.storage import StoredObject

            return StoredObject(chunks=iter([b"jpeg-data"]), content_type="image/jpeg")

    monkeypatch.setattr(attachment_api, "get_attachment_storage", lambda settings: FakeStorage())

    response = client.get(f"/api/attachments/{attachment.id}/content?token=dev-admin-token")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"


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
