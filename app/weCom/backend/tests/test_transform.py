from wecom_app.models import (
    CustomerChat,
    CustomerChatMember,
    EmployeeExternalContact,
    ExternalContact,
    Message,
    MessageRecipient,
    RawMessage,
)
from wecom_app.services.transform import backfill_single_conversations, transform_raw_message


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


def test_room_message_creates_minimal_customer_chat_for_sender(db):
    raw = RawMessage(
        seq=22,
        msgid="msg_room_text",
        msg_type="text",
        decrypt_payload={
            "msgtype": "text",
            "from": "wang_teacher",
            "tolist": ["external_xiaoyu"],
            "roomid": "room_from_message",
            "msgtime": 1781832840000,
            "text": {"content": "群里看一下这道题"},
        },
    )
    db.add(raw)
    db.flush()

    result = transform_raw_message(db, raw)
    db.commit()

    message = db.query(Message).filter_by(msgid="msg_room_text").one()
    chat = db.query(CustomerChat).filter_by(chat_id="room_from_message").one()
    member = db.query(CustomerChatMember).filter_by(
        chat_id="room_from_message",
        member_userid="wang_teacher",
    ).one()
    assert result == "message"
    assert message.conversation_type == "room"
    assert chat.status == "active"
    assert member.member_type == "employee"


def test_single_message_creates_minimal_external_contact_relation(db):
    raw = RawMessage(
        seq=23,
        msgid="msg_single_new_contact",
        msg_type="text",
        decrypt_payload={
            "msgtype": "text",
            "from": "XiaoTao",
            "tolist": ["wm_new_contact"],
            "msgtime": 1781832840000,
            "text": {"content": "你好"},
        },
    )
    db.add(raw)
    db.flush()

    transform_raw_message(db, raw)
    db.commit()

    contact = db.query(ExternalContact).filter_by(external_userid="wm_new_contact").one()
    rel = db.query(EmployeeExternalContact).filter_by(
        userid="XiaoTao",
        external_userid="wm_new_contact",
    ).one()
    assert contact.name == "wm_new_contact"
    assert rel.is_deleted is False


def test_backfills_external_contact_relation_from_existing_single_messages(db):
    db.query(EmployeeExternalContact).delete()
    db.query(ExternalContact).delete()
    raw = RawMessage(
        seq=24,
        msgid="msg_existing_single_raw",
        decrypt_payload={"msgtype": "text"},
        process_status="processed",
    )
    db.add(raw)
    db.flush()
    message = Message(
        raw_message_id=raw.id,
        seq=24,
        msgid="msg_existing_single",
        action="send",
        msg_type="text",
        conversation_type="single",
        sender_id="XiaoTao",
        sender_type="employee",
        content_text="历史消息",
        msg_time_ms=1781832840000,
        msg_time=raw.created_at,
        raw_payload={},
    )
    db.add(message)
    db.flush()
    db.add(
        MessageRecipient(
            message_id=message.id,
            msgid=message.msgid,
            recipient_id="wm_existing_contact",
            recipient_type="external_contact",
        )
    )
    db.commit()

    created = backfill_single_conversations(db)

    assert created >= 1
    db.query(EmployeeExternalContact).filter_by(
        userid="XiaoTao",
        external_userid="wm_existing_contact",
    ).one()


def test_backfill_single_conversations_deduplicates_relations_in_one_transaction(db):
    db.query(EmployeeExternalContact).delete()
    db.query(ExternalContact).delete()
    for idx in range(2):
        raw = RawMessage(
            seq=30 + idx,
            msgid=f"msg_dup_rel_raw_{idx}",
            decrypt_payload={"msgtype": "text"},
            process_status="processed",
        )
        db.add(raw)
        db.flush()
        message = Message(
            raw_message_id=raw.id,
            seq=30 + idx,
            msgid=f"msg_dup_rel_{idx}",
            action="send",
            msg_type="text",
            conversation_type="single",
            sender_id="XiaoTao",
            sender_type="employee",
            content_text="重复关系消息",
            msg_time_ms=1781832840000 + idx,
            msg_time=raw.created_at,
            raw_payload={},
        )
        db.add(message)
        db.flush()
        db.add(
            MessageRecipient(
                message_id=message.id,
                msgid=message.msgid,
                recipient_id="wm_dup_contact",
                recipient_type="external_contact",
            )
        )
    db.commit()

    backfill_single_conversations(db)

    assert (
        db.query(EmployeeExternalContact)
        .filter_by(userid="XiaoTao", external_userid="wm_dup_contact")
        .count()
        == 1
    )
