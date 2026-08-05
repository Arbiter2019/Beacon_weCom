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


def test_aliyun_oss_settings_normalize_prefix(monkeypatch):
    monkeypatch.setenv("ATTACHMENT_STORAGE_BACKEND", "aliyun_oss")
    monkeypatch.setenv("ALIYUN_OSS_ACCESS_KEY_ID", "ak")
    monkeypatch.setenv("ALIYUN_OSS_ACCESS_KEY_SECRET", "secret")
    monkeypatch.setenv("ALIYUN_OSS_BUCKET", "wecom-bucket")
    monkeypatch.setenv("ALIYUN_OSS_PREFIX", "/wecom")
    monkeypatch.setenv("ALIYUN_OSS_INTERNAL_ENDPOINT", "oss-cn-shanghai-internal.aliyuncs.com")
    monkeypatch.setenv("ALIYUN_OSS_PUBLIC_BASE_URL", "https://wecom-bucket.oss-cn-shanghai.aliyuncs.com")

    settings = Settings()

    assert settings.attachment_storage_backend == "aliyun_oss"
    assert settings.aliyun_oss_bucket == "wecom-bucket"
    assert settings.aliyun_oss_prefix_normalized == "wecom/"
    assert settings.aliyun_oss_internal_endpoint == "oss-cn-shanghai-internal.aliyuncs.com"


def test_worker_task_interval_defaults():
    settings = Settings()

    assert settings.worker_poll_interval_seconds == 60
    assert settings.contact_sync_interval_seconds == 1800
    assert settings.customer_chat_sync_interval_seconds == 1800
    assert settings.attachment_sync_interval_seconds == 600
