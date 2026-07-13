from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from wecom_app.api.deps import require_admin
from wecom_app.db.session import get_db
from wecom_app.models import Department, Employee, ObservableEmployeeScope
from wecom_app.schemas.archive import ObservableEmployeeOut, ObservableEmployeeUpsert

router = APIRouter(prefix="/api/observable-employees", dependencies=[Depends(require_admin)])


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
    return {
        "items": [
            ObservableEmployeeOut(
                userid=employee.userid,
                name=employee.name,
                avatar=employee.avatar,
                department=department_name,
                scope_status=scope.scope_status,
                conversation_count=0,
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
