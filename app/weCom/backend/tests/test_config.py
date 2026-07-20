from wecom_app.core.config import Settings


def test_customer_api_secret_prefers_explicit_api_secret(monkeypatch):
    monkeypatch.setenv("WECOM_CUSTOMER_API_SECRET", "new-secret")
    monkeypatch.setenv("WECOM_CUSTOMER_SECRET", "legacy-secret")

    settings = Settings()

    assert settings.wecom_customer_api_secret == "new-secret"
    assert settings.customer_api_secret == "new-secret"


def test_customer_api_secret_falls_back_to_legacy_secret(monkeypatch):
    monkeypatch.delenv("WECOM_CUSTOMER_API_SECRET", raising=False)
    monkeypatch.setenv("WECOM_CUSTOMER_SECRET", "legacy-secret")

    settings = Settings()

    assert settings.customer_api_secret == "legacy-secret"
