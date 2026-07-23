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


def test_attachment_content_accepts_query_token(client, db, tmp_path, monkeypatch):
    from wecom_app.core.config import get_settings

    message = db.query(Message).filter_by(msgid="msg_text_1").one()
    storage_key = "2026/06/19/query-token.image"
    path = tmp_path / storage_key
    path.parent.mkdir(parents=True)
    path.write_bytes(b"image-data")
    attachment = Attachment(
        message_id=message.id,
        msgid="msg_query_token_image",
        attachment_type="image",
        sdkfileid="sdk-query-token",
        storage_key=storage_key,
        download_status="downloaded",
    )
    db.add(attachment)
    db.commit()

    class FakeSettings:
        internal_admin_token = "dev-admin-token"
        attachment_storage_root = tmp_path

    client.app.dependency_overrides[get_settings] = lambda: FakeSettings()

    response = client.get(f"/api/attachments/{attachment.id}/content?token=dev-admin-token")

    assert response.status_code == 200
    assert response.content == b"image-data"
    client.app.dependency_overrides.pop(get_settings, None)


def test_attachment_content_serves_image_media_type(client, db, tmp_path, monkeypatch):
    from wecom_app.core.config import get_settings

    message = db.query(Message).filter_by(msgid="msg_text_1").one()
    storage_key = "2026/06/19/photo.image"
    path = tmp_path / storage_key
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\xff\xd8\xff\xe0jpeg-data")
    attachment = Attachment(
        message_id=message.id,
        msgid="msg_jpeg_image",
        attachment_type="image",
        sdkfileid="sdk-jpeg",
        storage_key=storage_key,
        download_status="downloaded",
    )
    db.add(attachment)
    db.commit()

    class FakeSettings:
        internal_admin_token = "dev-admin-token"
        attachment_storage_root = tmp_path

    client.app.dependency_overrides[get_settings] = lambda: FakeSettings()

    response = client.get(f"/api/attachments/{attachment.id}/content?token=dev-admin-token")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    client.app.dependency_overrides.pop(get_settings, None)


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


def test_download_pending_attachments_retries_failed_rows(db, tmp_path):
    message = db.query(Message).filter_by(msgid="msg_text_1").one()
    attachment = Attachment(
        message_id=message.id,
        msgid="msg_image_retry",
        attachment_type="image",
        sdkfileid="sdk-retry",
        download_status="failed",
    )
    db.add(attachment)
    db.commit()

    class FakeArchiveClient:
        def download_media(self, sdkfileid):
            assert sdkfileid == "sdk-retry"
            return b"retry-data"

    result = download_pending_attachments(db, FakeArchiveClient(), tmp_path, limit=10)

    db.refresh(attachment)
    assert result == {"processed": 1, "downloaded": 1, "failed": 0}
    assert attachment.download_status == "downloaded"
    assert (tmp_path / attachment.storage_key).read_bytes() == b"retry-data"


def test_download_pending_attachments_rebuilds_client_after_broken_pipe(db, tmp_path):
    message = db.query(Message).filter_by(msgid="msg_text_1").one()
    attachment = Attachment(
        message_id=message.id,
        msgid="msg_image_broken_pipe",
        attachment_type="image",
        sdkfileid="sdk-broken-pipe",
    )
    db.add(attachment)
    db.commit()

    clients = []

    class BrokenClient:
        def download_media(self, sdkfileid):
            assert sdkfileid == "sdk-broken-pipe"
            raise BrokenPipeError(32, "Broken pipe")

        def close(self):
            pass

    class HealthyClient:
        def download_media(self, sdkfileid):
            assert sdkfileid == "sdk-broken-pipe"
            return b"healthy-client-data"

        def close(self):
            pass

    def client_factory():
        client = BrokenClient() if not clients else HealthyClient()
        clients.append(client)
        return client

    result = download_pending_attachments(db, client_factory(), tmp_path, limit=10, client_factory=client_factory)

    db.refresh(attachment)
    assert result == {"processed": 1, "downloaded": 1, "failed": 0}
    assert len(clients) == 2
    assert attachment.download_status == "downloaded"
    assert (tmp_path / attachment.storage_key).read_bytes() == b"healthy-client-data"


def test_download_pending_attachments_uses_fresh_client_per_attachment_when_factory_is_available(db, tmp_path):
    message = db.query(Message).filter_by(msgid="msg_text_1").one()
    first = Attachment(
        message_id=message.id,
        msgid="msg_image_fresh_1",
        attachment_type="image",
        sdkfileid="sdk-fresh-1",
    )
    second = Attachment(
        message_id=message.id,
        msgid="msg_image_fresh_2",
        attachment_type="image",
        sdkfileid="sdk-fresh-2",
    )
    db.add_all([first, second])
    db.commit()

    clients = []

    class FreshClient:
        def __init__(self, index):
            self.index = index
            self.calls = 0

        def download_media(self, sdkfileid):
            self.calls += 1
            return f"{self.index}:{sdkfileid}".encode()

        def close(self):
            pass

    def client_factory():
        client = FreshClient(len(clients))
        clients.append(client)
        return client

    result = download_pending_attachments(db, client_factory(), tmp_path, limit=10, client_factory=client_factory)

    db.refresh(first)
    db.refresh(second)
    assert result == {"processed": 2, "downloaded": 2, "failed": 0}
    assert len(clients) == 2
    assert [client.calls for client in clients] == [1, 1]
    assert first.download_status == "downloaded"
    assert second.download_status == "downloaded"


def test_download_pending_attachments_marks_expired_media(db, tmp_path):
    message = db.query(Message).filter_by(msgid="msg_text_1").one()
    attachment = Attachment(
        message_id=message.id,
        msgid="msg_image_expired",
        attachment_type="image",
        sdkfileid="sdk-expired",
    )
    db.add(attachment)
    db.commit()

    class FakeArchiveClient:
        def download_media(self, sdkfileid):
            assert sdkfileid == "sdk-expired"
            raise RuntimeError("GetMediaData error code=10010")

    result = download_pending_attachments(db, FakeArchiveClient(), tmp_path, limit=10)

    db.refresh(attachment)
    assert result == {"processed": 1, "downloaded": 0, "failed": 1}
    assert attachment.download_status == "expired"
    assert attachment.download_error == "GetMediaData error code=10010"


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
