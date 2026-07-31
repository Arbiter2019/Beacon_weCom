from types import SimpleNamespace

from typer.testing import CliRunner

from analysis_app import cli
from analysis_app.cli import app


def test_run_command_dispatches_to_runner(monkeypatch):
    calls = {}

    def fake_run_analysis(**kwargs):
        calls["kwargs"] = kwargs
        return {"ok": True}

    monkeypatch.setattr(cli, "run_analysis", fake_run_analysis)

    result = CliRunner().invoke(
        app,
        [
            "run",
            "--start-date",
            "2026-07-21",
            "--end-date",
            "2026-07-21",
            "--userid",
            "wang_teacher",
            "--task",
            "basic",
            "--task",
            "response",
        ],
    )

    assert result.exit_code == 0
    assert calls["kwargs"]["observer_userid"] == "wang_teacher"
    assert calls["kwargs"]["tasks"] == ["basic", "response"]


def test_rollback_command_dispatches_to_rollbacker(monkeypatch):
    calls = {}

    def fake_rollback_analysis(**kwargs):
        calls["kwargs"] = kwargs
        return {"ok": True}

    monkeypatch.setattr(cli, "rollback_analysis", fake_rollback_analysis)

    result = CliRunner().invoke(
        app,
        [
            "rollback",
            "--start-date",
            "2026-07-21",
            "--end-date",
            "2026-07-22",
            "--task",
            "sentiment",
        ],
    )

    assert result.exit_code == 0
    assert calls["kwargs"]["tasks"] == ["sentiment"]
    assert calls["kwargs"]["start_date"].isoformat() == "2026-07-21"
    assert calls["kwargs"]["end_date"].isoformat() == "2026-07-22"


def test_llm_smoke_command_prints_success(monkeypatch):
    settings = object()
    calls = {}

    class FakeClient:
        def __init__(self, passed_settings):
            calls["settings"] = passed_settings

    def fake_smoke_test_llm(client, passed_settings):
        calls["client"] = client
        calls["smoke_settings"] = passed_settings
        return {"ok": True, "response": {"ok": True, "message": "pong"}}

    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    monkeypatch.setattr(cli, "OpenAICompatibleLLMClient", FakeClient)
    monkeypatch.setattr(cli, "smoke_test_llm", fake_smoke_test_llm)

    result = CliRunner().invoke(app, ["llm-smoke"])

    assert result.exit_code == 0
    assert calls["settings"] is settings
    assert calls["smoke_settings"] is settings
    assert calls["client"].__class__ is FakeClient
    assert '"ok": true' in result.stdout


def test_llm_smoke_command_exits_nonzero_on_error(monkeypatch):
    settings = SimpleNamespace(
        llm_provider="qwen",
        llm_model="kimi-k2.6",
        llm_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    monkeypatch.setattr(cli, "OpenAICompatibleLLMClient", lambda settings: object())
    monkeypatch.setattr(cli, "smoke_test_llm", lambda client, settings: (_ for _ in ()).throw(RuntimeError("boom")))

    result = CliRunner().invoke(app, ["llm-smoke"])

    assert result.exit_code == 1
    assert '"ok": false' in result.stdout
    assert '"error": "boom"' in result.stdout


def test_module_execution_invokes_typer_app():
    import os
    import subprocess
    import sys

    env = dict(os.environ)
    env["PYTHONPATH"] = ".:../weCom/backend"

    result = subprocess.run(
        [sys.executable, "-m", "analysis_app.cli", "--help"],
        cwd="/Users/xuwei/Desktop/morpheus/Projects/Beacon/WeCom/app/analysis",
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Operate WeCom analysis tasks" in result.stdout
