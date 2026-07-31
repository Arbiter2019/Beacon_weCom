from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from analysis_app.models import Base as AnalysisBase
from wecom_app.db.base import Base as ArchiveBase
from wecom_app.models import (
    CustomerChat,
    CustomerChatMember,
    Employee,
    EmployeeExternalContact,
    ExternalContact,
    Message,
    MessageRecipient,
    ObservableEmployeeScope,
    RawMessage,
)


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    ArchiveBase.metadata.create_all(engine)
    AnalysisBase.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    seed_data(session)
    yield session
    session.close()


def seed_data(db: Session) -> None:
    db.add_all(
        [
            Employee(userid="wang_teacher", name="王老师", main_department_id=1),
            Employee(userid="li_teacher", name="李老师", main_department_id=1),
            Employee(userid="disabled_teacher", name="停用老师", main_department_id=1),
        ]
    )
    db.add_all(
        [
            ObservableEmployeeScope(userid="wang_teacher", scope_status="enabled"),
            ObservableEmployeeScope(userid="li_teacher", scope_status="enabled"),
            ObservableEmployeeScope(userid="disabled_teacher", scope_status="disabled"),
        ]
    )
    db.add_all(
        [
            ExternalContact(external_userid="external_xiaoyu", name="小雨"),
            ExternalContact(external_userid="external_math", name="数学家长"),
            ExternalContact(external_userid="external_group_file", name="文件同学"),
        ]
    )
    db.add(
        EmployeeExternalContact(
            userid="wang_teacher",
            external_userid="external_xiaoyu",
            remark="沈晓雨",
            description="初三学员",
        )
    )
    db.add(
        EmployeeExternalContact(
            userid="li_teacher",
            external_userid="external_xiaoyu",
            remark="沈晓雨",
            description="同一学员的另一位老师视角",
        )
    )
    db.add(
        CustomerChat(
            chat_id="chat_math",
            name="初三数学群",
            owner_userid="wang_teacher",
            member_count=3,
            status="active",
        )
    )
    db.add_all(
        [
            CustomerChatMember(
                chat_id="chat_math",
                member_userid="wang_teacher",
                member_type="employee",
                role="owner",
                is_active=True,
            ),
            CustomerChatMember(
                chat_id="chat_math",
                member_userid="li_teacher",
                member_type="employee",
                role="member",
                group_nickname="李老师群名片",
                is_active=True,
            ),
            CustomerChatMember(
                chat_id="chat_math",
                member_userid="external_math",
                member_type="external_contact",
                group_nickname="张同学",
                role="member",
                is_active=True,
            ),
        ]
    )

    private_raw_1 = RawMessage(seq=1, msgid="msg_private_ext", decrypt_payload={"msgtype": "text"})
    private_raw_2 = RawMessage(seq=2, msgid="msg_private_emp", decrypt_payload={"msgtype": "text"})
    group_raw_1 = RawMessage(seq=3, msgid="msg_group_ext_1", decrypt_payload={"msgtype": "text"})
    group_raw_2 = RawMessage(seq=4, msgid="msg_group_li", decrypt_payload={"msgtype": "text"})
    group_raw_3 = RawMessage(seq=5, msgid="msg_group_ext_2", decrypt_payload={"msgtype": "text"})
    group_raw_4 = RawMessage(seq=6, msgid="msg_group_wang", decrypt_payload={"msgtype": "text"})
    db.add_all([private_raw_1, private_raw_2, group_raw_1, group_raw_2, group_raw_3, group_raw_4])
    db.flush()

    private_external = Message(
        raw_message_id=private_raw_1.id,
        seq=1,
        msgid="msg_private_ext",
        action="send",
        msg_type="text",
        conversation_type="single",
        sender_id="external_xiaoyu",
        sender_type="external_contact",
        sender_name="小雨",
        content_text="老师，今天作业怎么做？",
        msg_time_ms=1781865900000,
        msg_time=datetime(2026, 7, 20, 16, 5),
        raw_payload={"msgtype": "text"},
    )
    private_employee = Message(
        raw_message_id=private_raw_2.id,
        seq=2,
        msgid="msg_private_emp",
        action="send",
        msg_type="text",
        conversation_type="single",
        sender_id="wang_teacher",
        sender_type="employee",
        sender_name="王老师",
        content_text="先看第二题。",
        msg_time_ms=1781866500000,
        msg_time=datetime(2026, 7, 20, 16, 15),
        raw_payload={"msgtype": "text"},
    )
    group_ext_1 = Message(
        raw_message_id=group_raw_1.id,
        seq=3,
        msgid="msg_group_ext_1",
        action="send",
        msg_type="text",
        conversation_type="room",
        roomid="chat_math",
        sender_id="external_math",
        sender_type="external_contact",
        sender_name="数学家长",
        content_text="老师，这题怎么做？",
        msg_time_ms=1781833200000,
        msg_time=datetime(2026, 7, 20, 23, 0),
        raw_payload={"roomid": "chat_math", "msgtype": "text"},
    )
    group_li = Message(
        raw_message_id=group_raw_2.id,
        seq=4,
        msgid="msg_group_li",
        action="send",
        msg_type="text",
        conversation_type="room",
        roomid="chat_math",
        sender_id="li_teacher",
        sender_type="employee",
        sender_name="李老师",
        content_text="大家先做一下这道题。",
        msg_time_ms=1781833620000,
        msg_time=datetime(2026, 7, 20, 23, 7),
        raw_payload={"roomid": "chat_math", "msgtype": "text"},
    )
    group_ext_2 = Message(
        raw_message_id=group_raw_3.id,
        seq=5,
        msgid="msg_group_ext_2",
        action="send",
        msg_type="text",
        conversation_type="room",
        roomid="chat_math",
        sender_id="external_math",
        sender_type="external_contact",
        sender_name="数学家长",
        content_text="那这道题呢？",
        msg_time_ms=1781842200000,
        msg_time=datetime(2026, 7, 21, 1, 30),
        raw_payload={"roomid": "chat_math", "msgtype": "text"},
    )
    group_wang = Message(
        raw_message_id=group_raw_4.id,
        seq=6,
        msgid="msg_group_wang",
        action="send",
        msg_type="text",
        conversation_type="room",
        roomid="chat_math",
        sender_id="wang_teacher",
        sender_type="employee",
        sender_name="王老师",
        content_text="第二个知识点再讲一下。",
        msg_time_ms=1781844300000,
        msg_time=datetime(2026, 7, 21, 2, 5),
        raw_payload={"roomid": "chat_math", "msgtype": "text"},
    )
    db.add_all([private_external, private_employee, group_ext_1, group_li, group_ext_2, group_wang])
    db.flush()
    db.add_all(
        [
            MessageRecipient(
                message_id=private_external.id,
                msgid=private_external.msgid,
                recipient_id="wang_teacher",
                recipient_type="employee",
            ),
            MessageRecipient(
                message_id=private_employee.id,
                msgid=private_employee.msgid,
                recipient_id="external_xiaoyu",
                recipient_type="external_contact",
            ),
        ]
    )
    db.commit()
