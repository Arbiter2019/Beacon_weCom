from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Iterable

from analysis_app.config import load_settings
from analysis_app.db import create_session_makers, initialize_analysis_schema
from analysis_app.services.basic_stats import run_basic_stats
from analysis_app.services.hotwords import run_hotwords
from analysis_app.services.question_classification import run_question_classification
from analysis_app.services.response_stats import run_response_stats
from analysis_app.services.sentiment import run_sentiment_analysis
from analysis_app.services.snapshot import build_daily_snapshot

TASK_ORDER = ("snapshot", "basic", "response", "sentiment", "hotwords", "question")


def _date_range(start_date: date, end_date: date) -> Iterable[date]:
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _selected_tasks(tasks: list[str] | None) -> list[str]:
    if not tasks:
        return list(TASK_ORDER)
    return [task for task in TASK_ORDER if task in tasks]


def run_analysis(
    start_date: date,
    end_date: date,
    observer_userid: str | None = None,
    tasks: list[str] | None = None,
) -> dict:
    settings = load_settings()
    _archive_engine, analysis_engine, archive_session_maker, analysis_session_maker = create_session_makers(settings)
    initialize_analysis_schema(analysis_engine)
    selected_tasks = _selected_tasks(tasks)
    results: list[dict] = []

    def _run_task(task_name: str, day: date):
        try:
            with archive_session_maker() as archive_db, analysis_session_maker() as analysis_db:
                if task_name == "snapshot":
                    rows = build_daily_snapshot(archive_db, analysis_db, day, observer_userid)
                    return {"task": task_name, "date": day.isoformat(), "status": "success", "rows": len(rows)}
                if task_name == "basic":
                    rows = run_basic_stats(archive_db, analysis_db, day, observer_userid)
                    return {
                        "task": task_name,
                        "date": day.isoformat(),
                        "status": "success",
                        "rows": rows["rows_written"],
                    }
                if task_name == "response":
                    rows = run_response_stats(archive_db, analysis_db, day, observer_userid)
                    return {"task": task_name, "date": day.isoformat(), "status": "success", "rows": len(rows["rows"])}
                if task_name == "sentiment":
                    from analysis_app.llm_client import OpenAICompatibleLLMClient

                    client = OpenAICompatibleLLMClient(settings)
                    rows = run_sentiment_analysis(archive_db, analysis_db, day, client, observer_userid)
                    return {
                        "task": task_name,
                        "date": day.isoformat(),
                        "status": "success",
                        "rows": rows["detail_rows_written"],
                        "daily_rows": rows["daily_rows_written"],
                    }
                if task_name == "hotwords":
                    rows = run_hotwords(archive_db, analysis_db, day, observer_userid, settings.hotword_stopwords_path)
                    return {
                        "task": task_name,
                        "date": day.isoformat(),
                        "status": "success",
                        "rows": rows["rows_written"],
                    }
                if task_name == "question":
                    from analysis_app.llm_client import OpenAICompatibleLLMClient

                    client = OpenAICompatibleLLMClient(settings)
                    rows = run_question_classification(archive_db, analysis_db, day, client, observer_userid)
                    return {
                        "task": task_name,
                        "date": day.isoformat(),
                        "status": "success",
                        "rows": rows["rows_written"],
                    }
                raise ValueError(f"unsupported task: {task_name}")
        except Exception as exc:
            return {
                "task": task_name,
                "date": day.isoformat(),
                "status": "failed",
                "rows": 0,
                "error": str(exc),
            }

    for day in _date_range(start_date, end_date):
        with archive_session_maker() as archive_db, analysis_session_maker() as analysis_db:
            snapshot_rows = build_daily_snapshot(archive_db, analysis_db, day, observer_userid)
        if "snapshot" in selected_tasks:
            results.append({"task": "snapshot", "date": day.isoformat(), "status": "success", "rows": len(snapshot_rows)})
        downstream = [task for task in selected_tasks if task != "snapshot"]
        if downstream:
            with ThreadPoolExecutor(max_workers=min(len(downstream), settings.analysis_max_workers)) as executor:
                futures = [executor.submit(_run_task, task_name, day) for task_name in downstream]
                for future in futures:
                    results.append(future.result())

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "observer_userid": observer_userid,
        "tasks": selected_tasks,
        "results": results,
    }
