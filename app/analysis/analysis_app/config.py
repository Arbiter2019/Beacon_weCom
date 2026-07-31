from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ANALYSIS_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


@dataclass(frozen=True)
class AnalysisSettings:
    archive_database_url: str
    analysis_database_url: str
    llm_provider: str = "qwen"
    llm_api_key: str = ""
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "kimi-k2.6"
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.1
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 3
    analysis_timezone: str = "Asia/Shanghai"
    analysis_max_workers: int = 4
    hotword_stopwords_path: str | None = None


def load_settings() -> AnalysisSettings:
    load_dotenv(ANALYSIS_ENV_PATH, override=False)
    return AnalysisSettings(
        archive_database_url=os.getenv(
            "ARCHIVE_DATABASE_URL",
            "sqlite:///../weCom/backend/wecom_archive_local.db",
        ),
        analysis_database_url=os.getenv(
            "ANALYSIS_DATABASE_URL",
            "sqlite:///./wecom_analysis.db",
        ),
        llm_provider=os.getenv("LLM_PROVIDER", "qwen"),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        llm_model=os.getenv("LLM_MODEL", "kimi-k2.6"),
        llm_max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2048")),
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
        llm_timeout_seconds=int(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
        llm_max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
        analysis_timezone=os.getenv("ANALYSIS_TIMEZONE", "Asia/Shanghai"),
        analysis_max_workers=int(os.getenv("ANALYSIS_MAX_WORKERS", "4")),
        hotword_stopwords_path=os.getenv("HOTWORD_STOPWORDS_PATH") or None,
    )
