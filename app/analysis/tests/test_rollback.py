from datetime import date
from types import SimpleNamespace

from sqlalchemy.orm import sessionmaker

from analysis_app.models import MessageDailyStats
from analysis_app.services.basic_stats import run_basic_stats
from analysis_app.services import rollback as rollback_module


def test_rollback_deletes_only_selected_observer_and_task(db, monkeypatch):
    run_basic_stats(db, db, date(2026, 7, 21), observer_userid="wang_teacher")
    run_basic_stats(db, db, date(2026, 7, 21), observer_userid="li_teacher")
    before = db.query(MessageDailyStats).count()
    assert before == 4

    engine = db.get_bind()
    session_factory = sessionmaker(bind=engine)
    monkeypatch.setattr(
        rollback_module,
        "load_settings",
        lambda: SimpleNamespace(archive_database_url="sqlite://", analysis_database_url="sqlite://"),
    )
    monkeypatch.setattr(
        rollback_module,
        "create_session_makers",
        lambda settings: (engine, engine, session_factory, session_factory),
    )

    result = rollback_module.rollback_analysis(
        start_date=date(2026, 7, 21),
        end_date=date(2026, 7, 21),
        observer_userid="wang_teacher",
        tasks=["basic"],
    )

    assert result["tasks"] == ["basic"]
    remaining = db.query(MessageDailyStats).all()
    assert len(remaining) == 2
    assert {row.observer_userid for row in remaining} == {"li_teacher"}
