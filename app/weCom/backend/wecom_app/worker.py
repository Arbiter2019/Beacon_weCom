import logging
import time
from typing import Any

from wecom_app.core.config import get_settings
from wecom_app.db.session import SessionLocal
from wecom_app.services.attachments import backfill_image_attachments, download_pending_attachments
from wecom_app.services.external_contact_sync import sync_customer_chats, sync_external_contacts
from wecom_app.services.storage import get_attachment_storage
from wecom_app.services.sync_jobs import sync_messages_once
from wecom_app.wecom.client import WeComArchiveClient
from wecom_app.wecom.customer_client import WeComCustomerClient

logger = logging.getLogger(__name__)


def run_once(task_type: str = "message") -> dict:
    with SessionLocal() as db:
        if task_type == "message":
            result = sync_messages_once(db)
            return {"task": task_type, **result.__dict__}
        if task_type == "contacts":
            settings = get_settings()
            if not settings.customer_api_secret:
                return {
                    "task": task_type,
                    "fetched": 0,
                    "processed": 0,
                    "message": "customer api secret not configured",
                    "errors": [{"config": "WECOM_CUSTOMER_API_SECRET"}],
                }
            client = WeComCustomerClient(settings.wecom_corp_id, settings.customer_api_secret)
            result = sync_external_contacts(db, client)
            return {
                "task": task_type,
                "fetched": result["synced_contacts"],
                "processed": result["synced_contacts"],
                "message": "external contacts sync completed",
                "errors": result["errors"],
            }
        if task_type == "attachments":
            settings = get_settings()
            storage = get_attachment_storage(settings)
            backfill_result = backfill_image_attachments(db)
            download_result = download_pending_attachments(db, WeComArchiveClient, storage)
            return {
                "task": task_type,
                "message": "attachment sync completed",
                "backfilled": backfill_result["created"],
                "processed": download_result["processed"],
                "downloaded": download_result["downloaded"],
                "failed": download_result["failed"],
                "expired": download_result["expired"],
                "skipped": download_result["skipped"],
            }
        if task_type == "customer-chat":
            settings = get_settings()
            if not settings.customer_api_secret:
                return {
                    "task": task_type,
                    "fetched": 0,
                    "processed": 0,
                    "message": "customer api secret not configured",
                    "errors": [{"config": "WECOM_CUSTOMER_API_SECRET"}],
                }
            client = WeComCustomerClient(settings.wecom_corp_id, settings.customer_api_secret)
            result = sync_customer_chats(db, client)
            return {
                "task": task_type,
                "fetched": result["synced_chats"],
                "processed": result["synced_chats"],
                "message": "customer chats sync completed",
                "errors": result["errors"],
            }
        raise ValueError(f"unsupported sync task: {task_type}")


def _should_run(last_runs: dict[str, float], task_name: str, interval_seconds: float, now: float) -> bool:
    last_run = last_runs.get(task_name)
    return last_run is None or now - last_run >= interval_seconds


def _skip_result(task_name: str, last_runs: dict[str, float], interval_seconds: float, now: float) -> dict:
    last_run = last_runs.get(task_name)
    next_run = None if last_run is None else last_run + interval_seconds
    wait_seconds = 0 if next_run is None else max(next_run - now, 0)
    return {
        "task": task_name,
        "skipped": True,
        "reason": "interval_not_due",
        "next_run_in_seconds": wait_seconds,
    }


def run_scheduled_cycle(
    settings,
    archive_client: WeComArchiveClient | None,
    customer_client: WeComCustomerClient | None,
    last_runs: dict[str, float],
    now: float | None = None,
) -> dict[str, Any]:
    current_time = time.monotonic() if now is None else now
    results: dict[str, Any] = {}

    with SessionLocal() as db:
        results["message"] = sync_messages_once(db, client=archive_client)

    if customer_client is not None and _should_run(
        last_runs, "contacts", settings.contact_sync_interval_seconds, current_time
    ):
        with SessionLocal() as db:
            results["contacts"] = sync_external_contacts(db, customer_client)
        last_runs["contacts"] = current_time
    else:
        results["contacts"] = _skip_result(
            "contacts", last_runs, settings.contact_sync_interval_seconds, current_time
        )

    if customer_client is not None and _should_run(
        last_runs, "customer-chat", settings.customer_chat_sync_interval_seconds, current_time
    ):
        with SessionLocal() as db:
            results["customer-chat"] = sync_customer_chats(db, customer_client)
        last_runs["customer-chat"] = current_time
    else:
        results["customer-chat"] = _skip_result(
            "customer-chat", last_runs, settings.customer_chat_sync_interval_seconds, current_time
        )

    if archive_client is not None and _should_run(
        last_runs, "attachments", settings.attachment_sync_interval_seconds, current_time
    ):
        storage = get_attachment_storage(settings)
        with SessionLocal() as db:
            backfill_result = backfill_image_attachments(db)
        with SessionLocal() as db:
            download_result = download_pending_attachments(db, WeComArchiveClient, storage)
        results["attachments"] = {
            "task": "attachments",
            "backfill": backfill_result,
            "download": download_result,
        }
        last_runs["attachments"] = current_time
    else:
        results["attachments"] = _skip_result(
            "attachments", last_runs, settings.attachment_sync_interval_seconds, current_time
        )

    return results


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()

    # Create the SDK client once and reuse across poll cycles to avoid
    # repeatedly spawning subprocesses.
    client: WeComArchiveClient | None = None
    customer_client: WeComCustomerClient | None = None
    try:
        client = WeComArchiveClient()
    except Exception as exc:
        logger.error("SDK client init failed, will retry each cycle: %s", exc)
    if settings.customer_api_secret:
        try:
            customer_client = WeComCustomerClient(settings.wecom_corp_id, settings.customer_api_secret)
        except Exception as exc:
            logger.error("customer api client init failed, will skip contact sync: %s", exc)

    last_runs: dict[str, float] = {}
    while True:
        try:
            results = run_scheduled_cycle(settings, client, customer_client, last_runs)
            logger.info("sync result: %s", results["message"])
            logger.info("contacts sync result: %s", results["contacts"])
            logger.info("customer chat sync result: %s", results["customer-chat"])
            logger.info("attachment sync result: %s", results["attachments"])
        except Exception as exc:
            logger.error("worker cycle error: %s", exc)
        time.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    main()
