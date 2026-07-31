from datetime import date
from types import SimpleNamespace

from sqlalchemy.orm import sessionmaker

from analysis_app.services import runner as runner_module


def test_run_analysis_records_failed_task_without_dropping_successful_tasks(db, monkeypatch):
    engine = db.get_bind()
    session_factory = sessionmaker(bind=engine)

    monkeypatch.setattr(
        runner_module,
        "load_settings",
        lambda: SimpleNamespace(analysis_max_workers=1, hotword_stopwords_path=None),
    )
    monkeypatch.setattr(
        runner_module,
        "create_session_makers",
        lambda settings: (engine, engine, session_factory, session_factory),
    )
    monkeypatch.setattr(runner_module, "initialize_analysis_schema", lambda analysis_engine: None)

    def fail_sentiment(*args, **kwargs):
        raise RuntimeError("Client error '403 Forbidden'")

    monkeypatch.setattr(runner_module, "run_sentiment_analysis", fail_sentiment)

    result = runner_module.run_analysis(
        start_date=date(2026, 7, 21),
        end_date=date(2026, 7, 21),
        observer_userid="wang_teacher",
        tasks=["basic", "sentiment"],
    )

    by_task = {item["task"]: item for item in result["results"]}
    assert by_task["basic"]["status"] == "success"
    assert by_task["sentiment"]["status"] == "failed"
    assert "403 Forbidden" in by_task["sentiment"]["error"]
