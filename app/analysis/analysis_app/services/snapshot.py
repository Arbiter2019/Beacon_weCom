from __future__ import annotations

from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from analysis_app.models import ConversationSnapshot
from wecom_app.models import CustomerChat, CustomerChatMember, EmployeeExternalContact, ExternalContact, ObservableEmployeeScope


def _enabled_observers(archive_db: Session, observer_userid: str | None = None) -> list[str]:
    stmt = select(ObservableEmployeeScope.userid).where(ObservableEmployeeScope.scope_status == "enabled")
    if observer_userid:
        stmt = stmt.where(ObservableEmployeeScope.userid == observer_userid)
    return list(archive_db.scalars(stmt.order_by(ObservableEmployeeScope.userid)).all())


def _private_snapshot_rows(archive_db: Session, analysis_date: date, observer_userid: str) -> list[ConversationSnapshot]:
    rows: list[ConversationSnapshot] = []
    stmt = (
        select(EmployeeExternalContact, ExternalContact)
        .join(ExternalContact, ExternalContact.external_userid == EmployeeExternalContact.external_userid)
        .where(
            EmployeeExternalContact.userid == observer_userid,
            EmployeeExternalContact.is_deleted.is_(False),
            ExternalContact.is_deleted.is_(False),
        )
        .order_by(EmployeeExternalContact.remark, ExternalContact.name, ExternalContact.external_userid)
    )
    for rel, contact in archive_db.execute(stmt).all():
        rows.append(
            ConversationSnapshot(
                analysis_date=analysis_date,
                observer_userid=observer_userid,
                conversation_type="single",
                external_userid=contact.external_userid,
                roomid=None,
                display_name=rel.remark or contact.name or contact.external_userid,
                wechat_name=contact.name,
                member_count=1,
                snapshot_payload={
                    "relationship": {
                        "remark": rel.remark,
                        "description": rel.description,
                        "is_deleted": rel.is_deleted,
                    },
                    "contact": {
                        "external_userid": contact.external_userid,
                        "name": contact.name,
                    },
                },
            )
        )
    return rows


def _group_snapshot_rows(archive_db: Session, analysis_date: date, observer_userid: str) -> list[ConversationSnapshot]:
    rows: list[ConversationSnapshot] = []
    stmt = (
        select(CustomerChat, CustomerChatMember)
        .join(CustomerChatMember, CustomerChatMember.chat_id == CustomerChat.chat_id)
        .where(
            CustomerChatMember.member_userid == observer_userid,
            CustomerChatMember.is_active.is_(True),
            CustomerChat.status == "active",
        )
        .order_by(CustomerChat.name, CustomerChat.chat_id)
    )
    for chat, member in archive_db.execute(stmt).all():
        member_count = chat.member_count
        if member_count is None:
            member_count = archive_db.scalar(
                select(func.count()).select_from(CustomerChatMember).where(
                    CustomerChatMember.chat_id == chat.chat_id,
                    CustomerChatMember.is_active.is_(True),
                )
            ) or 0
        rows.append(
            ConversationSnapshot(
                analysis_date=analysis_date,
                observer_userid=observer_userid,
                conversation_type="room",
                external_userid=None,
                roomid=chat.chat_id,
                display_name=chat.name or chat.chat_id,
                wechat_name=chat.name,
                member_count=member_count,
                snapshot_payload={
                    "chat": {
                        "chat_id": chat.chat_id,
                        "name": chat.name,
                        "owner_userid": chat.owner_userid,
                        "status": chat.status,
                    },
                    "member": {
                        "member_userid": member.member_userid,
                        "role": member.role,
                        "member_type": member.member_type,
                    },
                },
            )
        )
    return rows


def build_daily_snapshot(
    archive_db: Session,
    analysis_db: Session,
    analysis_date: date,
    observer_userid: str | None = None,
) -> list[ConversationSnapshot]:
    observers = _enabled_observers(archive_db, observer_userid)
    if not observers:
        return []
    analysis_db.execute(
        delete(ConversationSnapshot).where(
            ConversationSnapshot.analysis_date == analysis_date,
            ConversationSnapshot.observer_userid.in_(observers),
        )
    )
    analysis_db.commit()
    analysis_db.expunge_all()

    rows: list[ConversationSnapshot] = []
    for userid in observers:
        rows.extend(_private_snapshot_rows(archive_db, analysis_date, userid))
        rows.extend(_group_snapshot_rows(archive_db, analysis_date, userid))
    analysis_db.add_all(rows)
    analysis_db.commit()
    return rows
