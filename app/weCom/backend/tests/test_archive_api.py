def test_requires_admin_token(client):
    response = client.get("/api/observable-employees")

    assert response.status_code == 401


def test_lists_observable_employees(client, auth_headers):
    response = client.get("/api/observable-employees", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["items"][0]["userid"] == "wang_teacher"
    assert response.json()["items"][0]["conversation_count"] == 2


def test_lists_directory_employees_for_observer_configuration(client, auth_headers):
    response = client.get("/api/directory-employees", headers=auth_headers)

    assert response.status_code == 200
    items = response.json()["items"]
    wang = next(item for item in items if item["userid"] == "wang_teacher")
    disabled = next(item for item in items if item["userid"] == "disabled_teacher")
    assert wang["scope_status"] == "enabled"
    assert wang["conversation_count"] == 2
    assert disabled["scope_status"] == "disabled"


def test_imports_observable_employees_csv(client, auth_headers):
    response = client.post(
        "/api/observable-employees/import",
        headers=auth_headers,
        files={
            "file": (
                "employees.csv",
                "userid,name,department_id,department_name,scope_status\nli_teacher,李老师,101,高中部,enabled\n",
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["imported"] == 1
    employees = client.get("/api/observable-employees", headers=auth_headers)
    userids = {item["userid"] for item in employees.json()["items"]}
    assert "li_teacher" in userids


def test_rejects_disabled_observed_user(client, auth_headers):
    response = client.get(
        "/api/observed-employees/disabled_teacher/conversations",
        headers=auth_headers,
    )

    assert response.status_code == 403


def test_lists_student_conversation_and_messages(client, auth_headers):
    conversations = client.get(
        "/api/observed-employees/wang_teacher/conversations?type=student",
        headers=auth_headers,
    )

    assert conversations.status_code == 200
    assert conversations.json()["items"][0]["display_name"] == "沈晓雨"

    messages = client.get(
        "/api/observed-employees/wang_teacher/student-conversations/external_xiaoyu/messages",
        headers=auth_headers,
    )
    assert messages.status_code == 200
    assert messages.json()["items"][0]["content"]["text"] == "先看交点"


def test_group_conversation_owner_uses_employee_name(db, client, auth_headers):
    from wecom_app.models import CustomerChat, Employee

    db.add(Employee(userid="XiaoHaiYan_3", name="小海燕老师", avatar="https://example.test/xhy.png"))
    chat = db.query(CustomerChat).filter_by(chat_id="chat_math").one()
    chat.owner_userid = "XiaoHaiYan_3"
    db.commit()

    response = client.get(
        "/api/observed-employees/wang_teacher/conversations?type=customer_chat",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["owner_name"] == "小海燕老师"


def test_conversations_return_cursor_for_next_page(db, client, auth_headers):
    from wecom_app.models import EmployeeExternalContact, ExternalContact

    for index in range(3):
        external_userid = f"external_page_{index}"
        db.add(ExternalContact(external_userid=external_userid, name=f"分页学员 {index}"))
        db.add(
            EmployeeExternalContact(
                userid="wang_teacher",
                external_userid=external_userid,
                remark=f"分页学员 {index}",
            )
        )
    db.commit()

    first_response = client.get(
        "/api/observed-employees/wang_teacher/conversations?type=student&limit=2",
        headers=auth_headers,
    )

    assert first_response.status_code == 200
    first_page = first_response.json()
    assert len(first_page["items"]) == 2
    assert first_page["next_cursor"] is not None

    second_response = client.get(
        "/api/observed-employees/wang_teacher/conversations"
        f"?type=student&limit=2&cursor={first_page['next_cursor']}",
        headers=auth_headers,
    )

    assert second_response.status_code == 200
    second_page = second_response.json()
    assert len(second_page["items"]) == 2
    first_ids = {item["external_userid"] for item in first_page["items"]}
    second_ids = {item["external_userid"] for item in second_page["items"]}
    assert first_ids.isdisjoint(second_ids)
    assert second_page["next_cursor"] is None


def test_group_detail_resolves_employee_and_external_member_names(db, client, auth_headers):
    from wecom_app.models import CustomerChatMember, Employee, ExternalContact

    db.add(Employee(userid="li_teacher", name="李老师", avatar="https://example.test/li.png"))
    db.add(ExternalContact(external_userid="wm_student", name="微信昵称", avatar="https://example.test/wm.png"))
    db.add(
        CustomerChatMember(
            chat_id="chat_math",
            member_userid="li_teacher",
            member_type="employee",
            role="member",
        )
    )
    db.add(
        CustomerChatMember(
            chat_id="chat_math",
            member_userid="wm_student",
            member_type="external_contact",
            group_nickname="群昵称",
            role="member",
        )
    )
    db.commit()

    response = client.get(
        "/api/observed-employees/wang_teacher/customer-chats/chat_math",
        headers=auth_headers,
    )

    assert response.status_code == 200
    members = {item["member_userid"]: item for item in response.json()["members"]}
    assert members["li_teacher"]["name"] == "李老师"
    assert members["li_teacher"]["avatar"] == "https://example.test/li.png"
    assert members["wm_student"]["name"] == "群昵称"
    assert members["wm_student"]["avatar"] == "https://example.test/wm.png"


def test_group_detail_uses_member_name_when_external_contact_is_id_fallback(db, client, auth_headers):
    from wecom_app.models import CustomerChatMember, ExternalContact

    db.add(
        ExternalContact(
            external_userid="wm_fallback_student",
            name="wm_fallback_student",
            raw_payload={"source": "message_fallback"},
        )
    )
    db.add(
        CustomerChatMember(
            chat_id="chat_math",
            member_userid="wm_fallback_student",
            member_type="external_contact",
            name="微信学员名",
            group_nickname=None,
            role="member",
        )
    )
    db.commit()

    response = client.get(
        "/api/observed-employees/wang_teacher/customer-chats/chat_math",
        headers=auth_headers,
    )

    assert response.status_code == 200
    members = {item["member_userid"]: item for item in response.json()["members"]}
    assert members["wm_fallback_student"]["name"] == "微信学员名"


def test_group_message_sender_uses_actual_employee_identity(db, client, auth_headers):
    from datetime import datetime

    from wecom_app.models import CustomerChatMember, Employee, Message, RawMessage

    db.add(Employee(userid="li_teacher", name="李老师", avatar="https://example.test/li.png"))
    db.add(
        CustomerChatMember(
            chat_id="chat_math",
            member_userid="li_teacher",
            member_type="employee",
            name="李老师群名片",
            role="member",
        )
    )
    raw = RawMessage(seq=31, msgid="msg_group_li_raw", decrypt_payload={"msgtype": "text"})
    db.add(raw)
    db.flush()
    db.add(
        Message(
            raw_message_id=raw.id,
            seq=31,
            msgid="msg_group_li",
            action="send",
            msg_type="text",
            conversation_type="room",
            roomid="chat_math",
            sender_id="li_teacher",
            sender_type="employee",
            content_text="这条不是观测员工发的",
            msg_time_ms=1781836440000,
            msg_time=datetime(2026, 6, 19, 10, 34),
            raw_payload={"roomid": "chat_math"},
        )
    )
    db.commit()

    response = client.get(
        "/api/observed-employees/wang_teacher/customer-chat-conversations/chat_math/messages",
        headers=auth_headers,
    )

    assert response.status_code == 200
    message = next(item for item in response.json()["items"] if item["msgid"] == "msg_group_li")
    assert message["sender"] == {
        "id": "li_teacher",
        "type": "employee",
        "display_name": "李老师群名片",
        "avatar": "https://example.test/li.png",
    }


def test_group_message_sender_uses_external_member_group_identity(db, client, auth_headers):
    from datetime import datetime

    from wecom_app.models import CustomerChatMember, Message, RawMessage

    db.add(
        CustomerChatMember(
            chat_id="chat_math",
            member_userid="wm_not_friend",
            member_type="external_contact",
            name="微信学员名",
            group_nickname="群内小明",
            role="member",
        )
    )
    raw = RawMessage(seq=32, msgid="msg_group_external_raw", decrypt_payload={"msgtype": "text"})
    db.add(raw)
    db.flush()
    db.add(
        Message(
            raw_message_id=raw.id,
            seq=32,
            msgid="msg_group_external",
            action="send",
            msg_type="text",
            conversation_type="room",
            roomid="chat_math",
            sender_id="wm_not_friend",
            sender_type="external_contact",
            content_text="我不是观测账号好友",
            msg_time_ms=1781836500000,
            msg_time=datetime(2026, 6, 19, 10, 35),
            raw_payload={"roomid": "chat_math"},
        )
    )
    db.commit()

    response = client.get(
        "/api/observed-employees/wang_teacher/customer-chat-conversations/chat_math/messages",
        headers=auth_headers,
    )

    assert response.status_code == 200
    message = next(item for item in response.json()["items"] if item["msgid"] == "msg_group_external")
    assert message["sender"]["display_name"] == "群内小明"


def test_group_messages_default_to_recent_page_and_cursor_loads_older(db, client, auth_headers):
    from datetime import datetime, timedelta

    from wecom_app.models import Message, RawMessage

    base_time = datetime(2026, 6, 19, 8, 0)
    for index in range(60):
        seq = 100 + index
        raw = RawMessage(seq=seq, msgid=f"raw_group_page_{index}", decrypt_payload={"msgtype": "text"})
        db.add(raw)
        db.flush()
        db.add(
            Message(
                raw_message_id=raw.id,
                seq=seq,
                msgid=f"msg_group_page_{index}",
                action="send",
                msg_type="text",
                conversation_type="room",
                roomid="chat_math",
                sender_id="wang_teacher",
                sender_type="employee",
                content_text=f"第 {index} 条",
                msg_time_ms=1781827200000 + index * 60000,
                msg_time=base_time + timedelta(minutes=index),
                raw_payload={"roomid": "chat_math"},
            )
        )
    db.commit()

    response = client.get(
        "/api/observed-employees/wang_teacher/customer-chat-conversations/chat_math/messages",
        headers=auth_headers,
    )

    assert response.status_code == 200
    page = response.json()
    assert [item["msgid"] for item in page["items"][:2]] == ["msg_group_page_10", "msg_group_page_11"]
    assert page["items"][-1]["msgid"] == "msg_group_page_59"
    assert page["next_cursor"] is not None

    older_response = client.get(
        "/api/observed-employees/wang_teacher/customer-chat-conversations/chat_math/messages"
        f"?cursor={page['next_cursor']}",
        headers=auth_headers,
    )

    assert older_response.status_code == 200
    older_page = older_response.json()
    assert [item["msgid"] for item in older_page["items"]] == [
        f"msg_group_page_{index}" for index in range(10)
    ]
    assert older_page["next_cursor"] is None


def test_search_is_scoped_to_current_conversation(client, auth_headers):
    response = client.get(
        "/api/observed-employees/wang_teacher/conversations/student/external_xiaoyu/message-search?keyword=交点",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["msgid"] == "msg_text_1"
