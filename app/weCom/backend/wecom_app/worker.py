import logging
import time

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

    while True:
        try:
            with SessionLocal() as db:
                result = sync_messages_once(db, client=client)
            logger.info("sync result: %s", result)
        except Exception as exc:
            logger.error("sync cycle error: %s", exc)
        try:
            if customer_client is not None:
                with SessionLocal() as db:
                    contacts_result = sync_external_contacts(db, customer_client)
                logger.info("contacts sync result: %s", contacts_result)
        except Exception as exc:
            logger.error("contacts sync cycle error: %s", exc)
        try:
            if customer_client is not None:
                with SessionLocal() as db:
                    chat_result = sync_customer_chats(db, customer_client)
                logger.info("customer chat sync result: %s", chat_result)
        except Exception as exc:
            logger.error("customer chat sync cycle error: %s", exc)
        try:
            if client is not None:
                with SessionLocal() as db:
                    backfill_result = backfill_image_attachments(db)
                logger.info("attachment backfill result: %s", backfill_result)
                with SessionLocal() as db:
                    storage = get_attachment_storage(settings)
                    attachment_result = download_pending_attachments(db, WeComArchiveClient, storage)
                logger.info("attachment download result: %s", attachment_result)
        except Exception as exc:
            logger.error("attachment sync cycle error: %s", exc)
        time.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    main()
