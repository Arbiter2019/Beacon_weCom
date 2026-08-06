import logging

import pytest

from analysis_app.config import AnalysisSettings
from analysis_app.llm_client import LLMResponseError, OpenAICompatibleLLMClient


def _settings(**overrides):
    values = {
        "archive_database_url": "sqlite:///archive.db",
        "analysis_database_url": "sqlite:///analysis.db",
        "llm_api_key": "test-key",
        "llm_base_url": "https://example.test/v1",
        "llm_model": "kimi/kimi-k2.5",
        "llm_max_retries": 2,
        "llm_response_format": "json_object",
        "llm_enable_thinking": False,
    }
    values.update(overrides)
    return AnalysisSettings(**values)


class FakeResponse:
    status_code = 200

    def __init__(self, content):
        self._content = content
        self.text = f"raw:{content}"

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


class FakeHTTPClient:
    requests = []
    responses = []

    def __init__(self, base_url, timeout):
        self.base_url = base_url
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, path, headers, json):
        self.requests.append({"path": path, "headers": headers, "json": json})
        return self.responses.pop(0)


def test_post_uses_json_mode_and_disables_thinking(monkeypatch):
    FakeHTTPClient.requests = []
    FakeHTTPClient.responses = [FakeResponse('{"items": []}')]
    monkeypatch.setattr("analysis_app.llm_client.httpx.Client", FakeHTTPClient)

    result = OpenAICompatibleLLMClient(_settings()).analyze_questions("JSON only", [])

    assert result == {"items": []}
    body = FakeHTTPClient.requests[0]["json"]
    assert body["model"] == "kimi/kimi-k2.5"
    assert body["response_format"] == {"type": "json_object"}
    assert body["enable_thinking"] is False


def test_question_retries_invalid_json_and_logs_raw_content(monkeypatch, caplog):
    FakeHTTPClient.requests = []
    FakeHTTPClient.responses = [
        FakeResponse("好的，以下是 JSON"),
        FakeResponse("```json\n{}\n```"),
        FakeResponse(
            '{"items": [{"msgid": "m1", "is_question": true, "category": "course", "confidence": 0.9, "reason": "问课程"}]}'
        ),
    ]
    monkeypatch.setattr("analysis_app.llm_client.httpx.Client", FakeHTTPClient)

    with caplog.at_level(logging.WARNING, logger="analysis_app.llm_client"):
        result = OpenAICompatibleLLMClient(_settings()).analyze_questions("JSON only", [{"msgid": "m1"}])

    assert result["items"][0]["category"] == "course"
    assert len(FakeHTTPClient.requests) == 3
    assert "attempt=1" in caplog.text
    assert "attempt=2" in caplog.text
    assert "raw_content" in caplog.text
    assert "以下是 JSON" in caplog.text


def test_question_fails_after_retries_with_last_raw_content(monkeypatch, caplog):
    FakeHTTPClient.requests = []
    FakeHTTPClient.responses = [
        FakeResponse("not-json-1"),
        FakeResponse("not-json-2"),
        FakeResponse("not-json-3"),
    ]
    monkeypatch.setattr("analysis_app.llm_client.httpx.Client", FakeHTTPClient)

    with caplog.at_level(logging.WARNING, logger="analysis_app.llm_client"):
        with pytest.raises(LLMResponseError) as exc_info:
            OpenAICompatibleLLMClient(_settings()).analyze_questions("JSON only", [{"msgid": "m1"}])

    assert len(FakeHTTPClient.requests) == 3
    assert "invalid JSON from LLM" in str(exc_info.value)
    assert "not-json-3" in str(exc_info.value)
    assert "not-json-3" in caplog.text


def test_question_retries_schema_validation_failure(monkeypatch):
    FakeHTTPClient.requests = []
    FakeHTTPClient.responses = [
        FakeResponse('{"items": [{"msgid": "m1", "category": "course"}]}'),
        FakeResponse(
            '{"items": [{"msgid": "m1", "is_question": false, "category": "uncategorized", "confidence": 0.7, "reason": "陈述"}]}'
        ),
    ]
    monkeypatch.setattr("analysis_app.llm_client.httpx.Client", FakeHTTPClient)

    result = OpenAICompatibleLLMClient(_settings(llm_max_retries=1)).analyze_questions("JSON only", [{"msgid": "m1"}])

    assert result["items"][0]["is_question"] is False
    assert len(FakeHTTPClient.requests) == 2
