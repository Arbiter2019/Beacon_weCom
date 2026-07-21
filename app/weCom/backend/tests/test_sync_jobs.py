from datetime import datetime

from wecom_app.models import CustomerChat, CustomerChatMember, Message, MessageRecipient, RawMessage, SyncCursor
from wecom_app.services.sync_jobs import sync_messages_once


class FakeArchiveClient:
    def __init__(self):
        self.calls = []

    def get_chat_data(self, seq: int, limit: int = 100):
        self.calls.append((seq, limit))
        if seq == 0:
            return (
                [
                    {
                        "seq": 1,
                        "msgid": "old_msg",
                        "msgtype": "text",
                        "from": "wang_teacher",
                        "tolist": ["external_xiaoyu"],
                        "msgtime": 1781832840000,
                        "text": {"content": "旧消息"},
                    },
                    {
                        "seq": 2,
                        "msgid": "new_msg",
                        "msgtype": "text",
                        "from": "external_xiaoyu",
                        "tolist": ["wang_teacher"],
                        "msgtime": 1781836440000,
                        "text": {"content": "新消息"},
                    },
                ],
                2,
            )
        return [], seq


class EmptyArchiveClient:
    def get_chat_data(self, seq: int, limit: int = 100):
        return [], seq


def test_initial_sync_drains_available_history_and_processes_newest_first(db):
    db.query(MessageRecipient).delete()
    db.query(Message).delete()
    db.query(RawMessage).delete()
    db.query(SyncCursor).delete()
    db.commit()
    client = FakeArchiveClient()

    result = sync_messages_once(db, client=client)

    messages = db.query(Message).order_by(Message.id).all()
    cursor = db.query(SyncCursor).filter_by(cursor_type="message_seq").one()
    assert result.fetched == 2
    assert client.calls == [(0, 1000), (2, 1000)]
    assert [message.msgid for message in messages] == ["new_msg", "old_msg"]
    assert cursor.cursor_value == "2"


def test_sync_skips_raw_message_when_seq_already_exists(db):
    db.query(MessageRecipient).delete()
    db.query(Message).delete()
    db.query(RawMessage).delete()
    db.query(SyncCursor).delete()
    existing = RawMessage(
        seq=1,
        msgid="existing_msg",
        decrypt_payload={"msgtype": "text"},
        process_status="processed",
    )
    db.add(existing)
    db.add(SyncCursor(cursor_type="message_seq", cursor_value="0"))
    db.commit()

    client = FakeArchiveClient()
    result = sync_messages_once(db, client=client)

    raws = db.query(RawMessage).order_by(RawMessage.seq).all()
    assert result.fetched == 2
    assert [(raw.seq, raw.msgid) for raw in raws] == [(1, "existing_msg"), (2, "new_msg")]


def test_sync_backfills_customer_chat_from_existing_room_messages(db):
    db.query(CustomerChatMember).delete()
    db.query(CustomerChat).delete()
    db.query(MessageRecipient).delete()
    db.query(Message).delete()
    db.query(RawMessage).delete()
    db.query(SyncCursor).delete()
    raw = RawMessage(
        seq=50,
        msgid="existing_room_raw",
        decrypt_payload={"msgtype": "text"},
        process_status="processed",
    )
    db.add(raw)
    db.flush()
    message = Message(
        raw_message_id=raw.id,
        seq=50,
        msgid="existing_room_msg",
        action="send",
        msg_type="text",
        conversation_type="room",
        roomid="existing_room",
        sender_id="wang_teacher",
        sender_type="employee",
        content_text="旧群消息",
        msg_time_ms=1781832840000,
        msg_time=datetime(2026, 6, 19, 9, 34),
        raw_payload={"roomid": "existing_room"},
    )
    db.add(message)
    db.commit()

    sync_messages_once(db, client=EmptyArchiveClient())

    chat = db.query(CustomerChat).filter_by(chat_id="existing_room").one()
    member = db.query(CustomerChatMember).filter_by(
        chat_id="existing_room",
        member_userid="wang_teacher",
    ).one()
    assert chat.status == "active"
    assert member.member_type == "employee"


def test_sync_does_not_report_database_lock_skip(db):
    db.query(MessageRecipient).delete()
    db.query(Message).delete()
    db.query(RawMessage).delete()
    db.query(SyncCursor).delete()
    db.commit()
    client = FakeArchiveClient()

    result = sync_messages_once(db, client=client)

    assert result.message == "message sync completed"
    assert client.calls == [(0, 1000), (2, 1000)]
