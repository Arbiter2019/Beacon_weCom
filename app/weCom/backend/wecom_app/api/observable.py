from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from wecom_app.api.deps import require_admin
from wecom_app.db.session import get_db
from wecom_app.models import (
    CustomerChatMember,
    Department,
    Employee,
    EmployeeExternalContact,
    ObservableEmployeeScope,
)
from wecom_app.schemas.archive import ObservableEmployeeOut, ObservableEmployeeUpsert
from wecom_app.services.employee_import import import_employees_csv

router = APIRouter(prefix="/api/observable-employees", dependencies=[Depends(require_admin)])
directory_router = APIRouter(prefix="/api/directory-employees", dependencies=[Depends(require_admin)])


def _conversation_counts(db: Session, userids: list[str]) -> dict[str, int]:
    if not userids:
        return {}
    counts = dict.fromkeys(userids, 0)
    student_rows = db.execute(
        select(EmployeeExternalContact.userid, func.count(EmployeeExternalContact.id))
        .where(EmployeeExternalContact.userid.in_(userids), EmployeeExternalContact.is_deleted.is_(False))
        .group_by(EmployeeExternalContact.userid)
    ).all()
    chat_rows = db.execute(
        select(CustomerChatMember.member_userid, func.count(CustomerChatMember.id))
        .where(
            CustomerChatMember.member_userid.in_(userids),
            CustomerChatMember.is_active.is_(True),
        )
        .group_by(CustomerChatMember.member_userid)
    ).all()
    for userid, count in student_rows:
        counts[userid] = counts.get(userid, 0) + count
    for userid, count in chat_rows:
        counts[userid] = counts.get(userid, 0) + count
    return counts


@router.get("", response_model=dict)
def list_observable_employees(
    keyword: str = "",
    department_id: int | None = None,
    status: str = "enabled",
    db: Session = Depends(get_db),
) -> dict:
    stmt = (
        select(Employee, ObservableEmployeeScope, Department.name)
        .join(ObservableEmployeeScope, ObservableEmployeeScope.userid == Employee.userid)
        .outerjoin(Department, Department.department_id == Employee.main_department_id)
    )
    if status:
        stmt = stmt.where(ObservableEmployeeScope.scope_status == status)
    if department_id is not None:
        stmt = stmt.where(Employee.main_department_id == department_id)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(Employee.userid.like(like), Employee.name.like(like), Department.name.like(like)))
    rows = db.execute(stmt.order_by(Employee.name.asc(), Employee.userid.asc())).all()
    counts = _conversation_counts(db, [employee.userid for employee, _, _ in rows])
    return {
        "items": [
            ObservableEmployeeOut(
                userid=employee.userid,
                name=employee.name,
                avatar=employee.avatar,
                department=department_name,
                scope_status=scope.scope_status,
                conversation_count=counts.get(employee.userid, 0),
            ).model_dump()
            for employee, scope, department_name in rows
        ]
    }


@router.post("", response_model=dict)
def upsert_observable_employee(payload: ObservableEmployeeUpsert, db: Session = Depends(get_db)) -> dict:
    employee = db.scalar(select(Employee).where(Employee.userid == payload.userid))
    if employee is None:
        employee = Employee(userid=payload.userid, name=payload.userid, department_ids=[])
        db.add(employee)
    scope = db.scalar(select(ObservableEmployeeScope).where(ObservableEmployeeScope.userid == payload.userid))
    if scope is None:
        scope = ObservableEmployeeScope(userid=payload.userid)
        db.add(scope)
    scope.scope_status = payload.scope_status
    scope.scope_reason = payload.scope_reason
    db.commit()
    return {"userid": payload.userid, "scope_status": scope.scope_status}


@router.post("/import", response_model=dict)
async def import_observable_employees(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    suffix = Path(file.filename or "employees.csv").suffix or ".csv"
    with NamedTemporaryFile("wb", suffix=suffix, delete=True) as temp_file:
        temp_file.write(await file.read())
        temp_file.flush()
        return import_employees_csv(db, Path(temp_file.name))


@router.patch("/{userid}", response_model=dict)
def patch_observable_employee(userid: str, payload: ObservableEmployeeUpsert, db: Session = Depends(get_db)) -> dict:
    scope = db.scalar(select(ObservableEmployeeScope).where(ObservableEmployeeScope.userid == userid))
    if scope is None:
        scope = ObservableEmployeeScope(userid=userid)
        db.add(scope)
    scope.scope_status = payload.scope_status
    scope.scope_reason = payload.scope_reason
    db.commit()
    return {"userid": userid, "scope_status": scope.scope_status}


@directory_router.get("", response_model=dict)
def list_directory_employees(keyword: str = "", limit: int = 100, db: Session = Depends(get_db)) -> dict:
    stmt = (
        select(Employee, ObservableEmployeeScope, Department.name)
        .outerjoin(ObservableEmployeeScope, ObservableEmployeeScope.userid == Employee.userid)
        .outerjoin(Department, Department.department_id == Employee.main_department_id)
        .where(Employee.is_deleted.is_(False))
    )
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(Employee.userid.like(like), Employee.name.like(like), Department.name.like(like)))
    rows = db.execute(stmt.order_by(Employee.name.asc(), Employee.userid.asc()).limit(limit)).all()
    counts = _conversation_counts(db, [employee.userid for employee, _, _ in rows])
    return {
        "items": [
            ObservableEmployeeOut(
                userid=employee.userid,
                name=employee.name or employee.userid,
                avatar=employee.avatar,
                department=department_name,
                scope_status=scope.scope_status if scope else "disabled",
                conversation_count=counts.get(employee.userid, 0),
            ).model_dump()
            for employee, scope, department_name in rows
        ]
    }
