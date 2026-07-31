from collections.abc import Generator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from wecom_app.core.config import get_settings
from wecom_app.db import analysis_session
from wecom_app.db.base import Base
from wecom_app.db.session import get_db
from wecom_app.main import create_app
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
from analysis_app.models import Base as AnalysisBase


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    AnalysisBase.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    seed_data(session)
    yield session
    session.close()


@pytest.fixture()
def client(db: Session) -> TestClient:
    app = create_app()

    def override_db() -> Generator[Session, None, None]:
        yield db

    get_settings.cache_clear()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[analysis_session.get_analysis_db] = override_db
    return TestClient(app)


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer dev-admin-token"}


def seed_data(db: Session) -> None:
    teacher = Employee(userid="wang_teacher", name="小王老师", main_department_id=1)
    disabled_teacher = Employee(userid="disabled_teacher", name="停用老师", main_department_id=1)
    db.add_all([teacher, disabled_teacher])
    db.add(ObservableEmployeeScope(userid="wang_teacher", scope_status="enabled"))
    db.add(ObservableEmployeeScope(userid="disabled_teacher", scope_status="disabled"))
    contact = ExternalContact(external_userid="external_xiaoyu", name="小雨", avatar="")
    db.add(contact)
    db.add(
        EmployeeExternalContact(
            userid="wang_teacher",
            external_userid="external_xiaoyu",
            remark="沈晓雨",
            description="初三学员",
        )
    )
    chat = CustomerChat(
        chat_id="chat_math",
        name="初三数学群",
        owner_userid="wang_teacher",
        member_count=2,
        status="active",
    )
    db.add(chat)
    db.add(
        CustomerChatMember(
            chat_id="chat_math",
            member_userid="wang_teacher",
            member_type="employee",
            role="owner",
        )
    )
    raw = RawMessage(seq=1, msgid="msg_text_1", decrypt_payload={"msgtype": "text"})
    db.add(raw)
    db.flush()
    message = Message(
        raw_message_id=raw.id,
        seq=1,
        msgid="msg_text_1",
        action="send",
        msg_type="text",
        conversation_type="single",
        sender_id="wang_teacher",
        sender_type="employee",
        sender_name="小王老师",
        content_text="先看交点",
        msg_time_ms=1781832840000,
        msg_time=datetime(2026, 6, 19, 9, 34),
        raw_payload={"msgtype": "text"},
    )
    db.add(message)
    db.flush()
    db.add(
        MessageRecipient(
            message_id=message.id,
            msgid=message.msgid,
            recipient_id="external_xiaoyu",
            recipient_type="external_contact",
        )
    )
    db.commit()
