from analysis_app import config
from analysis_app.config import load_settings


def test_load_settings_reads_analysis_env_file(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "ARCHIVE_DATABASE_URL=mysql+pymysql://wecom:pw@127.0.0.1:3306/wecom_archive",
                "ANALYSIS_DATABASE_URL=mysql+pymysql://wecom:pw@127.0.0.1:3306/wecom_analysis",
                "LLM_MODEL=smoke-model",
                "LLM_RESPONSE_FORMAT=json_object",
                "LLM_ENABLE_THINKING=false",
                "ANALYSIS_MAX_WORKERS=7",
                "HOTWORD_STOPWORDS_PATH=/tmp/stopwords.txt",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "ANALYSIS_ENV_PATH", env_path, raising=False)
    monkeypatch.delenv("ARCHIVE_DATABASE_URL", raising=False)
    monkeypatch.delenv("ANALYSIS_DATABASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_RESPONSE_FORMAT", raising=False)
    monkeypatch.delenv("LLM_ENABLE_THINKING", raising=False)
    monkeypatch.delenv("ANALYSIS_MAX_WORKERS", raising=False)
    monkeypatch.delenv("HOTWORD_STOPWORDS_PATH", raising=False)

    settings = load_settings()

    assert settings.archive_database_url == "mysql+pymysql://wecom:pw@127.0.0.1:3306/wecom_archive"
    assert settings.analysis_database_url == "mysql+pymysql://wecom:pw@127.0.0.1:3306/wecom_analysis"
    assert settings.llm_model == "smoke-model"
    assert settings.llm_response_format == "json_object"
    assert settings.llm_enable_thinking is False
    assert settings.analysis_max_workers == 7
    assert settings.hotword_stopwords_path == "/tmp/stopwords.txt"


def test_load_settings_keeps_exported_env_priority_over_env_file(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("LLM_MODEL=from-file\n", encoding="utf-8")
    monkeypatch.setattr(config, "ANALYSIS_ENV_PATH", env_path, raising=False)
    monkeypatch.setenv("LLM_MODEL", "from-shell")

    settings = load_settings()

    assert settings.llm_model == "from-shell"
