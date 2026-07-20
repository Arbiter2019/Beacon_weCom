from typer.testing import CliRunner

from wecom_app import cli
from wecom_app.cli import app


def test_callback_urls_command_lists_paths():
    result = CliRunner().invoke(app, ["callback", "urls"])

    assert result.exit_code == 0
    assert "/callbacks/wecom/contact" in result.output
    assert "/callbacks/wecom/archive-event" in result.output


def test_import_employees_command_uses_csv_file(monkeypatch, tmp_path):
    csv_file = tmp_path / "employees.csv"
    csv_file.write_text("userid,name\nli_teacher,李老师\n", encoding="utf-8")
    calls = {}

    class FakeSession:
        def __enter__(self):
            return "db"

        def __exit__(self, exc_type, exc, traceback):
            return None

    def fake_import_employees_csv(db, path):
        calls["args"] = (db, path)
        return {"imported": 1, "created": 1, "updated": 0, "scoped": 0}

    monkeypatch.setattr(cli, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(cli, "import_employees_csv", fake_import_employees_csv)

    result = CliRunner().invoke(app, ["import", "employees", "--file", str(csv_file)])

    assert result.exit_code == 0
    assert calls["args"] == ("db", csv_file)
    assert '"imported": 1' in result.output
