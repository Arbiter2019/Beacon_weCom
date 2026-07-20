import csv
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from wecom_app.models import Department, Employee, ObservableEmployeeScope


VALID_SCOPE_STATUSES = {"enabled", "disabled"}


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _parse_int(value: str | None) -> int | None:
    value = _blank_to_none(value)
    if value is None:
        return None
    return int(value)


def import_employees_csv(db: Session, csv_path: Path) -> dict[str, Any]:
    imported = 0
    created = 0
    updated = 0
    scoped = 0
    errors: list[dict[str, Any]] = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row_number, row in enumerate(reader, start=2):
            userid = _blank_to_none(row.get("userid"))
            if userid is None:
                errors.append({"row": row_number, "error": "userid is required"})
                continue

            department_id = _parse_int(row.get("department_id"))
            department_name = _blank_to_none(row.get("department_name"))
            if department_id is not None and department_name is not None:
                department = db.scalar(
                    select(Department).where(Department.department_id == department_id)
                )
                if department is None:
                    department = Department(department_id=department_id, name=department_name)
                    db.add(department)
                else:
                    department.name = department_name

            employee = db.scalar(select(Employee).where(Employee.userid == userid))
            if employee is None:
                employee = Employee(userid=userid)
                db.add(employee)
                created += 1
            else:
                updated += 1

            employee.name = _blank_to_none(row.get("name")) or employee.name or userid
            employee.alias = _blank_to_none(row.get("alias")) or employee.alias
            employee.mobile = _blank_to_none(row.get("mobile")) or employee.mobile
            employee.email = _blank_to_none(row.get("email")) or employee.email
            employee.avatar = _blank_to_none(row.get("avatar")) or employee.avatar
            employee.position = _blank_to_none(row.get("position")) or employee.position
            employee.status = _parse_int(row.get("status")) if _blank_to_none(row.get("status")) else employee.status
            if department_id is not None:
                employee.main_department_id = department_id
                employee.department_ids = [department_id]

            scope_status = _blank_to_none(row.get("scope_status"))
            if scope_status is not None:
                if scope_status not in VALID_SCOPE_STATUSES:
                    errors.append(
                        {
                            "row": row_number,
                            "error": "scope_status must be enabled or disabled",
                        }
                    )
                    continue
                scope = db.scalar(
                    select(ObservableEmployeeScope).where(
                        ObservableEmployeeScope.userid == userid
                    )
                )
                if scope is None:
                    scope = ObservableEmployeeScope(userid=userid)
                    db.add(scope)
                scope.scope_status = scope_status
                scope.scope_reason = _blank_to_none(row.get("scope_reason"))
                scoped += 1

            imported += 1

    db.commit()
    result: dict[str, Any] = {
        "imported": imported,
        "created": created,
        "updated": updated,
        "scoped": scoped,
    }
    if errors:
        result["errors"] = errors
    return result
