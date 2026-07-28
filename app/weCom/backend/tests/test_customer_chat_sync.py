from wecom_app.models import CustomerChat, CustomerChatMember
from wecom_app.services.external_contact_sync import sync_customer_chats


class FakeCustomerChatClient:
    def list_customer_chats(self, owner_userid=None, cursor=""):
        assert owner_userid == "XiaoHaiYan_3"
        assert cursor == ""
        return {
            "group_chat_list": [
                {
                    "chat_id": "chat_alpha",
                }
            ],
            "next_cursor": "",
        }

    def get_customer_chat(self, chat_id):
        assert chat_id == "chat_alpha"
        return {
            "group_chat": {
                "chat_id": "chat_alpha",
                "name": "小海燕初三群",
                "owner": "XiaoHaiYan_3",
                "notice": "群公告",
                "admin_list": [{"userid": "assistant_teacher"}],
                "create_time": 1781832840,
                "member_list": [
                    {
                        "userid": "XiaoHaiYan_3",
                        "type": 1,
                        "name": "小海燕老师",
                        "join_time": 1781832840,
                        "role": 1,
                    },
                    {
                        "userid": "wm_student",
                        "type": 2,
                        "name": "微信学员",
                        "group_nickname": "小明",
                        "join_time": 1781832850,
                        "role": 2,
                    },
                ],
            }
        }


class FakeExistingFallbackChatClient:
    def list_customer_chats(self, owner_userid=None, cursor=""):
        assert owner_userid == "XiaoHaiYan_3"
        return {"group_chat_list": [], "next_cursor": ""}

    def get_customer_chat(self, chat_id):
        assert chat_id == "chat_fallback"
        return {
            "group_chat": {
                "chat_id": "chat_fallback",
                "name": "已同步群名",
                "owner": "other_teacher",
                "member_list": [
                    {"userid": "XiaoHaiYan_3", "type": 1, "name": "小海燕老师", "role": 2},
                    {"userid": "wm_student", "type": 2, "name": "群内学员", "role": 2},
                ],
            }
        }


def test_sync_customer_chats_upserts_chat_name_and_members(db):
    db.query(CustomerChatMember).delete()
    db.query(CustomerChat).delete()
    db.commit()

    result = sync_customer_chats(db, FakeCustomerChatClient(), owner_userids=["XiaoHaiYan_3"])

    chat = db.query(CustomerChat).filter_by(chat_id="chat_alpha").one()
    members = db.query(CustomerChatMember).filter_by(chat_id="chat_alpha").all()
    assert result == {"synced_owners": 1, "synced_chats": 1, "errors": []}
    assert chat.name == "小海燕初三群"
    assert chat.owner_userid == "XiaoHaiYan_3"
    assert chat.member_count == 2
    assert chat.admin_userids == ["assistant_teacher"]
    assert {member.member_userid for member in members} == {"XiaoHaiYan_3", "wm_student"}
    assert db.query(CustomerChatMember).filter_by(member_userid="wm_student").one().member_type == "external_contact"


def test_sync_customer_chats_refreshes_existing_member_fallback_chats(db):
    db.query(CustomerChatMember).delete()
    db.query(CustomerChat).delete()
    db.add(CustomerChat(chat_id="chat_fallback", name="chat_fallback", raw_payload={"source": "message_fallback"}))
    db.add(
        CustomerChatMember(
            chat_id="chat_fallback",
            member_userid="XiaoHaiYan_3",
            member_type="employee",
            is_active=True,
            raw_payload={"source": "message_fallback"},
        )
    )
    db.commit()

    result = sync_customer_chats(db, FakeExistingFallbackChatClient(), owner_userids=["XiaoHaiYan_3"])

    chat = db.query(CustomerChat).filter_by(chat_id="chat_fallback").one()
    assert result == {"synced_owners": 1, "synced_chats": 1, "errors": []}
    assert chat.name == "已同步群名"
    assert chat.owner_userid == "other_teacher"
    assert chat.member_count == 2
