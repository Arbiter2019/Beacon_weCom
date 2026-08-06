from types import SimpleNamespace

from analysis_app.llm_client import smoke_test_llm


class FakeSmokeClient:
    def _post(self, prompt, payload):
        return {"ok": True, "message": "pong"}


def test_smoke_test_llm_returns_success_payload():
    result = smoke_test_llm(
        FakeSmokeClient(),
        SimpleNamespace(
            llm_provider="qwen",
            llm_model="kimi/kimi-k2.5",
            llm_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
    )

    assert result["ok"] is True
    assert result["provider"] == "qwen"
    assert result["model"] == "kimi/kimi-k2.5"
    assert result["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert result["response"] == {"ok": True, "message": "pong"}
