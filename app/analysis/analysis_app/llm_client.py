from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Callable

import httpx

from analysis_app.config import AnalysisSettings
from analysis_app.question_categories import load_question_categories


logger = logging.getLogger(__name__)


class LLMResponseError(RuntimeError):
    pass


Validator = Callable[[dict], None]


def _preview(value: object, limit: int = 2000) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text[:limit]


def _require_items(response: dict, task_type: str) -> list[dict]:
    items = response.get("items")
    if not isinstance(items, list):
        raise LLMResponseError(f"{task_type} LLM response must contain an items array")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise LLMResponseError(f"{task_type} LLM item[{index}] must be an object")
    return items


def _validate_sentiment_response(response: dict) -> None:
    valid_sentiments = {"positive", "neutral", "negative"}
    for index, item in enumerate(_require_items(response, "sentiment")):
        for field in ("msgid", "sentiment", "confidence", "reason"):
            if field not in item:
                raise LLMResponseError(f"sentiment LLM item[{index}] missing field: {field}")
        if item["sentiment"] not in valid_sentiments:
            raise LLMResponseError(f"sentiment LLM item[{index}] has invalid sentiment: {item['sentiment']}")
        if not isinstance(item["confidence"], (int, float)):
            raise LLMResponseError(f"sentiment LLM item[{index}] confidence must be a number")


def _validate_question_response(response: dict) -> None:
    valid_categories = {category.key for category in load_question_categories()}
    for index, item in enumerate(_require_items(response, "question")):
        for field in ("msgid", "is_question", "category", "confidence", "reason"):
            if field not in item:
                raise LLMResponseError(f"question LLM item[{index}] missing field: {field}")
        if not isinstance(item["is_question"], bool):
            raise LLMResponseError(f"question LLM item[{index}] is_question must be a boolean")
        if item["category"] not in valid_categories:
            raise LLMResponseError(f"question LLM item[{index}] has invalid category: {item['category']}")
        if not isinstance(item["confidence"], (int, float)):
            raise LLMResponseError(f"question LLM item[{index}] confidence must be a number")


@dataclass
class OpenAICompatibleLLMClient:
    settings: AnalysisSettings

    def _post(self, prompt: str, payload: dict, *, task_type: str = "llm", validator: Validator | None = None) -> dict:
        if not self.settings.llm_api_key:
            raise LLMResponseError("LLM_API_KEY is not configured")
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        max_attempts = max(1, self.settings.llm_max_retries + 1)
        last_error: Exception | None = None
        last_content: object = None
        for attempt in range(1, max_attempts + 1):
            response = None
            try:
                response = self._send_once(prompt, payload, headers)
                parsed = self._parse_response(response)
                last_content = parsed["raw_content"]
                result = parsed["json"]
                if validator:
                    validator(result)
                return result
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "LLM request failed task=%s attempt=%s/%s model=%s error=%s raw_content=%s raw_response=%s",
                    task_type,
                    attempt,
                    max_attempts,
                    self.settings.llm_model,
                    exc,
                    _preview(last_content),
                    _preview(getattr(response, "text", "")),
                )
                if attempt == max_attempts:
                    break
        raw_suffix = f"; raw_content={_preview(last_content)}" if last_content is not None else ""
        raise LLMResponseError(f"{last_error}{raw_suffix}") from last_error

    def _send_once(self, prompt: str, payload: dict, headers: dict) -> httpx.Response:
        body = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            "temperature": self.settings.llm_temperature,
            "max_tokens": self.settings.llm_max_tokens,
        }
        if self.settings.llm_response_format == "json_object":
            body["response_format"] = {"type": "json_object"}
        if self.settings.llm_enable_thinking is not None:
            body["enable_thinking"] = self.settings.llm_enable_thinking
        with httpx.Client(base_url=self.settings.llm_base_url, timeout=self.settings.llm_timeout_seconds) as client:
            response = client.post("/chat/completions", headers=headers, json=body)
            response.raise_for_status()
            return response

    def _parse_response(self, response: httpx.Response) -> dict:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, dict):
            return {"json": content, "raw_content": content}
        if not isinstance(content, str):
            raise LLMResponseError("unsupported response content type")
        try:
            return {"json": json.loads(content), "raw_content": content}
        except json.JSONDecodeError as exc:
            raise LLMResponseError(f"invalid JSON from LLM: {exc}; raw_content={_preview(content)}") from exc

    def analyze_sentiment(self, prompt: str, messages: list[dict]) -> dict:
        return self._post(prompt, {"items": messages}, task_type="sentiment", validator=_validate_sentiment_response)

    def analyze_questions(self, prompt: str, messages: list[dict]) -> dict:
        return self._post(prompt, {"items": messages}, task_type="question", validator=_validate_question_response)


def smoke_test_llm(client: OpenAICompatibleLLMClient, settings: AnalysisSettings) -> dict:
    prompt = "\n".join(
        [
            "你是一个连通性测试助手。",
            "只输出合法 JSON，不允许 Markdown、解释文本或代码块。",
            '严格输出 {"ok": true, "message": "pong"}。',
        ]
    )
    response = client._post(prompt, {"ping": "pong"})
    return {
        "ok": True,
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "base_url": settings.llm_base_url,
        "response": response,
    }
