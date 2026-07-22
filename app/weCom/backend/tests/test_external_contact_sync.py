import pytest
from sqlalchemy.exc import IntegrityError

from wecom_app.models import Employee, EmployeeExternalContact, ExternalContact, ObservableEmployeeScope
from wecom_app.services.external_contact_sync import sync_external_contacts


class FakeCustomerClient:
    def list_external_contacts(self, userid):
        return ["wm_shared_contact"]

    def get_external_contact(self, external_userid):
        return {
            "external_contact": {
                "external_userid": external_userid,
                "name": "sunny",
                "avatar": "https://example.test/avatar.png",
                "type": 1,
                "gender": 2,
            },
            "follow_user": [
                {"userid": "wang_teacher", "remark": "王老师备注"},
                {"userid": "li_teacher", "remark": "李老师备注"},
            ],
        }


class DuplicateListCustomerClient(FakeCustomerClient):
    def list_external_contacts(self, userid):
        return ["wm_shared_contact", "wm_shared_contact"]


def test_sync_external_contacts_deduplicates_pending_contacts_when_autoflush_disabled(db):
    db.autoflush = False
    db.add(Employee(userid="li_teacher", name="李老师", department_ids=[]))
    db.add(ObservableEmployeeScope(userid="li_teacher", scope_status="enabled"))
    db.commit()

    try:
        result = sync_external_contacts(
            db,
            FakeCustomerClient(),
            userids=["wang_teacher", "li_teacher"],
        )
    except IntegrityError as exc:
        pytest.fail(f"sync should upsert shared external contacts idempotently: {exc}")

    assert result["synced_contacts"] == 2
    assert db.query(ExternalContact).filter_by(external_userid="wm_shared_contact").count() == 1
    assert (
        db.query(EmployeeExternalContact)
        .filter_by(external_userid="wm_shared_contact")
        .count()
        == 2
    )


def test_sync_external_contacts_deduplicates_duplicate_ids_for_same_employee(db):
    db.autoflush = False

    try:
        result = sync_external_contacts(
            db,
            DuplicateListCustomerClient(),
            userids=["wang_teacher"],
        )
    except IntegrityError as exc:
        pytest.fail(f"sync should ignore duplicate external ids for one employee: {exc}")

    assert result["synced_contacts"] == 1
    assert db.query(ExternalContact).filter_by(external_userid="wm_shared_contact").count() == 1
    assert (
        db.query(EmployeeExternalContact)
        .filter_by(userid="wang_teacher", external_userid="wm_shared_contact")
        .count()
        == 1
    )
