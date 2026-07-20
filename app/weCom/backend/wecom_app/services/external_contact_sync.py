"""Sync external contacts (客户) from WeCom API into local DB."""
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from wecom_app.models import Employee, EmployeeExternalContact, ExternalContact, ObservableEmployeeScope
from wecom_app.wecom.customer_client import WeComAPIError, WeComCustomerClient

logger = logging.getLogger(__name__)


def _upsert_external_contact(db: Session, ec_data: dict) -> ExternalContact:
    ext_id = ec_data["external_userid"]
    ec = db.scalar(select(ExternalContact).where(ExternalContact.external_userid == ext_id))
    if ec is None:
        ec = ExternalContact(external_userid=ext_id)
        db.add(ec)
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


def _upsert_relation(db: Session, userid: str, ext_id: str, follow_data: dict) -> None:
    rel = db.scalar(
        select(EmployeeExternalContact).where(
            EmployeeExternalContact.userid == userid,
            EmployeeExternalContact.external_userid == ext_id,
        )
    )
    if rel is None:
        rel = EmployeeExternalContact(userid=userid, external_userid=ext_id)
        db.add(rel)
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

        for ext_id in ext_ids:
            try:
                detail = client.get_external_contact(ext_id)
            except WeComAPIError as e:
                logger.warning("get_external_contact failed for %s: %s", ext_id, e)
                errors.append({"external_userid": ext_id, "error": str(e)})
                continue

            ec_data = detail.get("external_contact", {})
            ec_data["external_userid"] = ext_id   # ensure key is present
            _upsert_external_contact(db, ec_data)

            follow_data = next(
                (f for f in detail.get("follow_user", []) if f.get("userid") == userid),
                {},
            )
            _upsert_relation(db, userid, ext_id, follow_data)
            synced_contacts += 1

    db.commit()
    return {
        "synced_employees": len(userids),
        "synced_contacts": synced_contacts,
        "errors": errors,
    }
