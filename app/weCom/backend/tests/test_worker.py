from wecom_app import worker


def test_run_once_contacts_syncs_external_contacts(monkeypatch):
    calls = {}

    class FakeSettings:
        wecom_corp_id = "corp"
        customer_api_secret = "secret"

    class FakeSession:
        def __enter__(self):
            return "db"

        def __exit__(self, exc_type, exc, traceback):
            return None

    class FakeCustomerClient:
        def __init__(self, corp_id, secret):
            calls["client"] = (corp_id, secret)

    def fake_sync_external_contacts(db, client):
        calls["sync"] = (db, client)
        return {"synced_employees": 1, "synced_contacts": 2, "errors": []}

    monkeypatch.setattr(worker, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(worker, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(worker, "WeComCustomerClient", FakeCustomerClient)
    monkeypatch.setattr(worker, "sync_external_contacts", fake_sync_external_contacts)

    result = worker.run_once("contacts")

    assert calls["client"] == ("corp", "secret")
    assert calls["sync"][0] == "db"
    assert result == {
        "task": "contacts",
        "fetched": 2,
        "processed": 2,
        "message": "external contacts sync completed",
        "errors": [],
    }


def test_run_once_contacts_reports_missing_secret(monkeypatch):
    class FakeSettings:
        wecom_corp_id = "corp"
        customer_api_secret = ""

    class FakeSession:
        def __enter__(self):
            return "db"

        def __exit__(self, exc_type, exc, traceback):
            return None

    monkeypatch.setattr(worker, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(worker, "SessionLocal", lambda: FakeSession())

    result = worker.run_once("contacts")

    assert result == {
        "task": "contacts",
        "fetched": 0,
        "processed": 0,
        "message": "customer api secret not configured",
        "errors": [{"config": "WECOM_CUSTOMER_API_SECRET"}],
    }


def test_run_once_attachments_backfills_then_downloads(monkeypatch):
    calls = {}

    class FakeSettings:
        attachment_storage_root = "/data/attachments"

    class FakeSession:
        def __enter__(self):
            return "db"

        def __exit__(self, exc_type, exc, traceback):
            return None

    class FakeArchiveClient:
        def __init__(self):
            calls["client_init"] = True

    def fake_backfill_image_attachments(db):
        calls["backfill"] = db
        return {"processed": 3, "created": 2}

    def fake_download_pending_attachments(db, client, root):
        calls["download"] = (db, client, root)
        return {"processed": 2, "downloaded": 2, "failed": 0}

    monkeypatch.setattr(worker, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(worker, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(worker, "WeComArchiveClient", FakeArchiveClient)
    monkeypatch.setattr(worker, "backfill_image_attachments", fake_backfill_image_attachments)
    monkeypatch.setattr(worker, "download_pending_attachments", fake_download_pending_attachments)

    result = worker.run_once("attachments")

    assert calls["client_init"] is True
    assert calls["backfill"] == "db"
    assert calls["download"][0] == "db"
    assert result == {
        "task": "attachments",
        "message": "attachment sync completed",
        "backfilled": 2,
        "processed": 2,
        "downloaded": 2,
        "failed": 0,
    }
