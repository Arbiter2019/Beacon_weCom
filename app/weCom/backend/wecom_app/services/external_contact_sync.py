"""Sync external contacts (客户) from WeCom API into local DB."""
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from wecom_app.models import (
    CustomerChat,
    CustomerChatMember,
    Employee,
    EmployeeExternalContact,
    ExternalContact,
    ObservableEmployeeScope,
)
from wecom_app.wecom.customer_client import WeComAPIError, WeComCustomerClient

logger = logging.getLogger(__name__)
CONTACTS_SYNC_LOCK_NAME = "wecom_sync_external_contacts"
CONTACTS_SYNC_LOCK_TIMEOUT_SECONDS = 60
CUSTOMER_CHAT_SYNC_LOCK_NAME = "wecom_sync_customer_chats"
CUSTOMER_CHAT_SYNC_LOCK_TIMEOUT_SECONDS = 60


@contextmanager
def _contacts_sync_lock(db: Session):
    bind = db.get_bind()
    dialect_name = bind.dialect.name if bind is not None else ""
    if dialect_name not in {"mysql", "mariadb"}:
        yield True
        return

    acquired = db.scalar(
        text("SELECT GET_LOCK(:lock_name, :timeout_seconds)"),
        {
            "lock_name": CONTACTS_SYNC_LOCK_NAME,
            "timeout_seconds": CONTACTS_SYNC_LOCK_TIMEOUT_SECONDS,
        },
    )
    try:
        yield acquired == 1
    finally:
        if acquired == 1:
            db.execute(text("SELECT RELEASE_LOCK(:lock_name)"), {"lock_name": CONTACTS_SYNC_LOCK_NAME})


@contextmanager
def _customer_chat_sync_lock(db: Session):
    bind = db.get_bind()
    dialect_name = bind.dialect.name if bind is not None else ""
    if dialect_name not in {"mysql", "mariadb"}:
        yield True
        return

    acquired = db.scalar(
        text("SELECT GET_LOCK(:lock_name, :timeout_seconds)"),
        {
            "lock_name": CUSTOMER_CHAT_SYNC_LOCK_NAME,
            "timeout_seconds": CUSTOMER_CHAT_SYNC_LOCK_TIMEOUT_SECONDS,
        },
    )
    try:
        yield acquired == 1
    finally:
        if acquired == 1:
            db.execute(text("SELECT RELEASE_LOCK(:lock_name)"), {"lock_name": CUSTOMER_CHAT_SYNC_LOCK_NAME})


def _upsert_external_contact(
    db: Session,
    ec_data: dict,
    cache: dict[str, ExternalContact],
) -> ExternalContact:
    ext_id = ec_data["external_userid"]
    ec = cache.get(ext_id)
    if ec is None:
        ec = db.scalar(select(ExternalContact).where(ExternalContact.external_userid == ext_id))
        if ec is not None:
            cache[ext_id] = ec
    if ec is None:
        ec = ExternalContact(external_userid=ext_id)
        db.add(ec)
        cache[ext_id] = ec
    ec.name = ec_data.get("name")
    ec.avatar = ec_data.get("avatar")
    ec.type = ec_data.get("type")
    ec.gender = ec_data.get("gender")
    ec.unionid = ec_data.get("unionid")
    ec.corp_name = ec_data.get("corp_name")
    ec.corp_full_name = ec_data.get("corp_full_name")
    ec.raw_payload = ec_data
    ec.last_synced_at = datetime.utcnow()
    return ec


def _upsert_relation(
    db: Session,
    userid: str,
    ext_id: str,
    follow_data: dict,
    cache: dict[tuple[str, str], EmployeeExternalContact],
) -> None:
    relation_key = (userid, ext_id)
    rel = cache.get(relation_key)
    if rel is None:
        rel = db.scalar(
            select(EmployeeExternalContact).where(
                EmployeeExternalContact.userid == userid,
                EmployeeExternalContact.external_userid == ext_id,
            )
        )
        if rel is not None:
            cache[relation_key] = rel
    if rel is None:
        rel = EmployeeExternalContact(userid=userid, external_userid=ext_id)
        db.add(rel)
        cache[relation_key] = rel
    rel.remark = follow_data.get("remark")
    rel.description = follow_data.get("description")
    rel.remark_corp_name = follow_data.get("remark_corp_name")
    rel.remark_mobiles = follow_data.get("remark_mobiles")
    rel.tag_ids = [t.get("tag_id") for t in follow_data.get("tags", [])]
    rel.add_way = follow_data.get("add_way")
    add_time = follow_data.get("createtime")
    if add_time:
        rel.add_time_ms = int(add_time) * 1000
        rel.add_time = datetime.utcfromtimestamp(int(add_time))
    rel.raw_payload = follow_data
    rel.last_synced_at = datetime.utcnow()


def sync_external_contacts(
    db: Session,
    client: WeComCustomerClient,
    userids: list[str] | None = None,
) -> dict[str, Any]:
    """
    Pull all external contacts for observable employees and upsert into DB.

    Args:
        db: database session
        client: WeComCustomerClient (customer API secret required)
        userids: optional list of employee userids to sync; defaults to all enabled observable employees
    """
    with _contacts_sync_lock(db) as lock_acquired:
        if not lock_acquired:
            return {
                "synced_employees": 0,
                "synced_contacts": 0,
                "errors": [{"lock": CONTACTS_SYNC_LOCK_NAME, "error": "contacts sync lock timeout"}],
            }

        if userids is None:
            userids = list(
                db.scalars(
                    select(ObservableEmployeeScope.userid).where(
                        ObservableEmployeeScope.scope_status == "enabled"
                    )
                )
            )

        synced_contacts = 0
        errors: list[dict] = []
        external_contact_cache: dict[str, ExternalContact] = {}
        relation_cache: dict[tuple[str, str], EmployeeExternalContact] = {}

        for userid in userids:
            # Ensure Employee row exists
            if not db.scalar(select(Employee).where(Employee.userid == userid)):
                db.add(Employee(userid=userid, name=userid, department_ids=[]))

            try:
                ext_ids = client.list_external_contacts(userid)
            except WeComAPIError as e:
                logger.warning("list_external_contacts failed for %s: %s", userid, e)
                errors.append({"userid": userid, "error": str(e)})
                continue

            logger.info("employee %s has %d external contacts", userid, len(ext_ids))

            seen_ext_ids: set[str] = set()
            for ext_id in ext_ids:
                if ext_id in seen_ext_ids:
                    continue
                seen_ext_ids.add(ext_id)

                try:
                    detail = client.get_external_contact(ext_id)
                except WeComAPIError as e:
                    logger.warning("get_external_contact failed for %s: %s", ext_id, e)
                    errors.append({"external_userid": ext_id, "error": str(e)})
                    continue

                ec_data = detail.get("external_contact", {})
                ec_data["external_userid"] = ext_id   # ensure key is present
                _upsert_external_contact(db, ec_data, external_contact_cache)

                follow_data = next(
                    (f for f in detail.get("follow_user", []) if f.get("userid") == userid),
                    {},
                )
                _upsert_relation(db, userid, ext_id, follow_data, relation_cache)
                synced_contacts += 1

        db.commit()
        return {
            "synced_employees": len(userids),
            "synced_contacts": synced_contacts,
            "errors": errors,
        }


def _upsert_customer_chat(db: Session, chat_data: dict) -> CustomerChat:
    chat_id = chat_data["chat_id"]
    chat = db.scalar(select(CustomerChat).where(CustomerChat.chat_id == chat_id))
    if chat is None:
        chat = CustomerChat(chat_id=chat_id)
        db.add(chat)
    chat.name = chat_data.get("name")
    chat.owner_userid = chat_data.get("owner")
    chat.notice = chat_data.get("notice")
    chat.member_count = len(chat_data.get("member_list", []) or [])
    admins = [item.get("userid") for item in chat_data.get("admin_list", []) if item.get("userid")]
    chat.admin_userids = admins
    create_time = chat_data.get("create_time")
    if create_time:
        chat.create_time = datetime.utcfromtimestamp(int(create_time))
        chat.create_time_ms = int(create_time) * 1000
    chat.status = "active"
    chat.raw_payload = chat_data
    chat.last_synced_at = datetime.utcnow()
    return chat


def _upsert_customer_chat_member(db: Session, chat_id: str, member_data: dict) -> None:
    member_userid = member_data.get("userid")
    if not member_userid:
        return
    member_type = "employee" if member_data.get("type") == 1 else "external_contact"
    member = db.scalar(
        select(CustomerChatMember).where(
            CustomerChatMember.chat_id == chat_id,
            CustomerChatMember.member_userid == member_userid,
        )
    )
    if member is None:
        member = CustomerChatMember(chat_id=chat_id, member_userid=member_userid, member_type=member_type)
        db.add(member)
    member.member_type = member_type
    member.name = member_data.get("name")
    member.group_nickname = member_data.get("group_nickname") or member_data.get("nickname")
    join_time = member_data.get("join_time")
    if join_time:
        member.join_time = datetime.utcfromtimestamp(int(join_time))
        member.join_time_ms = int(join_time) * 1000
    member.role = "owner" if member_data.get("role") == 1 else "member"
    member.invitor_userid = member_data.get("invitor_userid")
    member.is_active = True
    member.left_at = None
    member.raw_payload = member_data
    member.last_synced_at = datetime.utcnow()


def _sync_customer_chat_detail(
    db: Session,
    client: WeComCustomerClient,
    chat_id: str,
    errors: list[dict],
) -> bool:
    try:
        detail = client.get_customer_chat(chat_id)
    except WeComAPIError as e:
        logger.warning("get_customer_chat failed for %s: %s", chat_id, e)
        errors.append({"chat_id": chat_id, "error": str(e)})
        return False

    chat_data = detail.get("group_chat", {})
    chat_data.setdefault("chat_id", chat_id)
    _upsert_customer_chat(db, chat_data)
    for member_data in chat_data.get("member_list", []) or []:
        _upsert_customer_chat_member(db, chat_id, member_data)
    return True


def sync_customer_chats(
    db: Session,
    client: WeComCustomerClient,
    owner_userids: list[str] | None = None,
) -> dict[str, int | list[dict]]:
    with _customer_chat_sync_lock(db) as lock_acquired:
        if not lock_acquired:
            return {
                "synced_owners": 0,
                "synced_chats": 0,
                "errors": [{"lock": CUSTOMER_CHAT_SYNC_LOCK_NAME, "error": "customer chat sync lock timeout"}],
            }

        if owner_userids is None:
            owner_userids = list(
                db.scalars(
                    select(ObservableEmployeeScope.userid).where(
                        ObservableEmployeeScope.scope_status == "enabled"
                    )
                )
            )

        errors: list[dict] = []
        synced_chats = 0
        seen_chat_ids: set[str] = set()

        for owner_userid in owner_userids:
            cursor = ""
            while True:
                try:
                    payload = client.list_customer_chats(owner_userid, cursor)
                except WeComAPIError as e:
                    logger.warning("list_customer_chats failed for %s: %s", owner_userid, e)
                    errors.append({"userid": owner_userid, "error": str(e)})
                    break

                for item in payload.get("group_chat_list", []):
                    chat_id = item.get("chat_id")
                    if not chat_id or chat_id in seen_chat_ids:
                        continue
                    seen_chat_ids.add(chat_id)
                    if _sync_customer_chat_detail(db, client, chat_id, errors):
                        synced_chats += 1

                next_cursor = payload.get("next_cursor") or ""
                if not next_cursor or next_cursor == cursor:
                    break
                cursor = next_cursor

        fallback_chat_ids = db.scalars(
            select(CustomerChat.chat_id)
            .join(CustomerChatMember, CustomerChatMember.chat_id == CustomerChat.chat_id)
            .where(
                CustomerChatMember.member_userid.in_(owner_userids),
                CustomerChatMember.is_active.is_(True),
            )
            .distinct()
        ).all()
        for chat_id in fallback_chat_ids:
            if chat_id in seen_chat_ids:
                continue
            seen_chat_ids.add(chat_id)
            if _sync_customer_chat_detail(db, client, chat_id, errors):
                synced_chats += 1

        db.commit()
        return {"synced_owners": len(owner_userids), "synced_chats": synced_chats, "errors": errors}
