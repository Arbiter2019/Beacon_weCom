from __future__ import annotations

import json
from datetime import date

import typer

from analysis_app.config import load_settings
from analysis_app.llm_client import OpenAICompatibleLLMClient, smoke_test_llm
from analysis_app.services.rollback import rollback_analysis
from analysis_app.services.runner import run_analysis

app = typer.Typer(help="Operate WeCom analysis tasks.")


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


@app.command()
def run(
    start_date: str = typer.Option(..., "--start-date"),
    end_date: str = typer.Option(..., "--end-date"),
    userid: str | None = typer.Option(None, "--userid"),
    task: list[str] = typer.Option([], "--task"),
) -> None:
    result = run_analysis(
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
        observer_userid=userid,
        tasks=task or None,
    )
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command()
def rollback(
    start_date: str = typer.Option(..., "--start-date"),
    end_date: str = typer.Option(..., "--end-date"),
    userid: str | None = typer.Option(None, "--userid"),
    task: list[str] = typer.Option([], "--task"),
) -> None:
    result = rollback_analysis(
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
        observer_userid=userid,
        tasks=task or None,
    )
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command("llm-smoke")
def llm_smoke() -> None:
    settings = load_settings()
    try:
        result = smoke_test_llm(OpenAICompatibleLLMClient(settings), settings)
    except Exception as exc:
        result = {
            "ok": False,
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "base_url": settings.llm_base_url,
            "error": str(exc),
        }
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
        raise typer.Exit(1) from exc
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()
