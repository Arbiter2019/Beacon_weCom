from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from analysis_app.config import AnalysisSettings


class LLMResponseError(RuntimeError):
    pass


@dataclass
class OpenAICompatibleLLMClient:
    settings: AnalysisSettings

    def _post(self, prompt: str, payload: dict) -> dict:
        if not self.settings.llm_api_key:
            raise LLMResponseError("LLM_API_KEY is not configured")
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            "temperature": self.settings.llm_temperature,
            "max_tokens": self.settings.llm_max_tokens,
        }
        with httpx.Client(base_url=self.settings.llm_base_url, timeout=self.settings.llm_timeout_seconds) as client:
            response = client.post("/chat/completions", headers=headers, json=body)
            response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, dict):
            return content
        if not isinstance(content, str):
            raise LLMResponseError("unsupported response content type")
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMResponseError(f"invalid JSON from LLM: {exc}") from exc

    def analyze_sentiment(self, prompt: str, messages: list[dict]) -> dict:
        return self._post(prompt, {"items": messages})

    def analyze_questions(self, prompt: str, messages: list[dict]) -> dict:
        return self._post(prompt, {"items": messages})


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
