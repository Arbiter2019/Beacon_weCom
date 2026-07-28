from datetime import datetime

from wecom_app.models import Attachment, Message, RawMessage
from wecom_app.services.storage import build_attachment_storage_key


def test_build_attachment_storage_key_partitions_by_type(db):
    raw = RawMessage(seq=41, msgid="msg_image_raw", decrypt_payload={"msgtype": "image"})
    db.add(raw)
    db.flush()
    message = Message(
        raw_message_id=raw.id,
        seq=41,
        msgid="msg_image_key",
        action="send",
        msg_type="image",
        conversation_type="single",
        sender_id="wang_teacher",
        sender_type="employee",
        content_text="[图片]",
        msg_time_ms=1781833200000,
        msg_time=datetime(2026, 6, 19, 9, 40),
        raw_payload={"msgtype": "image"},
    )
    db.add(message)
    db.flush()
    attachment = Attachment(
        message_id=message.id,
        msgid=message.msgid,
        attachment_type="image",
        md5sum="abc123",
        file_ext="jpg",
    )
    db.add(attachment)
    db.commit()

    assert build_attachment_storage_key(attachment, "wecom/") == (
        f"wecom/image/2026/06/19/{attachment.id}_abc123.jpg"
    )
