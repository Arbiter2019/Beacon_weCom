from sqlalchemy import select

from wecom_app.models import Department, Employee, ObservableEmployeeScope
from wecom_app.services.employee_import import import_employees_csv


def test_import_employees_csv_upserts_departments_employees_and_scope(db, tmp_path):
    csv_file = tmp_path / "employees.csv"
    csv_file.write_text(
        "\n".join(
            [
                "userid,name,department_id,department_name,scope_status,scope_reason",
                "li_teacher,李老师,101,高中部,enabled,initial import",
                "wang_teacher,王老师,102,初中部,disabled,paused",
            ]
        ),
        encoding="utf-8",
    )

    result = import_employees_csv(db, csv_file)

    assert result == {"imported": 2, "created": 1, "updated": 1, "scoped": 2}
    li_teacher = db.scalar(select(Employee).where(Employee.userid == "li_teacher"))
    assert li_teacher is not None
    assert li_teacher.name == "李老师"
    assert li_teacher.main_department_id == 101
    assert li_teacher.department_ids == [101]

    department = db.scalar(select(Department).where(Department.department_id == 101))
    assert department is not None
    assert department.name == "高中部"

    wang_scope = db.scalar(
        select(ObservableEmployeeScope).where(ObservableEmployeeScope.userid == "wang_teacher")
    )
    assert wang_scope is not None
    assert wang_scope.scope_status == "disabled"
    assert wang_scope.scope_reason == "paused"


def test_import_employees_csv_rejects_missing_userid(db, tmp_path):
    csv_file = tmp_path / "employees.csv"
    csv_file.write_text("userid,name\n,无编号老师\n", encoding="utf-8")

    result = import_employees_csv(db, csv_file)

    assert result["imported"] == 0
    assert result["errors"] == [{"row": 2, "error": "userid is required"}]
