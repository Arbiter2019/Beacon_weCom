from wecom_app.models import Message, RawMessage
from wecom_app.services.transform import transform_raw_message


def test_transforms_unsupported_message_into_placeholder(db):
    raw = RawMessage(
        seq=20,
        msgid="msg_file",
        msg_type="file",
        decrypt_payload={"msgtype": "file", "from": "wang_teacher", "tolist": ["external_xiaoyu"], "msgtime": 1},
    )
    db.add(raw)
    db.flush()

    result = transform_raw_message(db, raw)
    db.commit()

    message = db.query(Message).filter_by(msgid="msg_file").one()
    assert result == "message"
    assert message.is_supported is False
    assert message.content_text == "暂不支持的 file 消息"
    assert raw.process_status == "ignored"


def test_recall_marks_original_message(db):
    raw = RawMessage(
        seq=21,
        msgid="msg_recall",
        msg_type="revoke",
        decrypt_payload={"msgtype": "revoke", "revoke": {"pre_msgid": "msg_text_1"}, "msgtime": 1},
    )
    db.add(raw)
    db.flush()

    result = transform_raw_message(db, raw)
    db.commit()

    original = db.query(Message).filter_by(msgid="msg_text_1").one()
    assert result == "recall"
    assert original.is_recalled is True
    assert original.recalled_at is not None
