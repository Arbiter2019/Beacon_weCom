import logging
import time

from wecom_app.core.config import get_settings
from wecom_app.db.session import SessionLocal
from wecom_app.services.sync_jobs import sync_messages_once

logger = logging.getLogger(__name__)


def run_once(task_type: str = "message") -> dict:
    with SessionLocal() as db:
        if task_type == "message":
            result = sync_messages_once(db)
            return {"task": task_type, **result.__dict__}
        if task_type in {"contacts", "customer-chat"}:
            return {"task": task_type, "fetched": 0, "processed": 0, "message": "stub task completed"}
        raise ValueError(f"unsupported sync task: {task_type}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()

    # Create the SDK client once and reuse across poll cycles to avoid
    # repeatedly spawning subprocesses.
    from wecom_app.wecom.client import WeComArchiveClient
    client: WeComArchiveClient | None = None
    try:
        client = WeComArchiveClient()
    except Exception as exc:
        logger.error("SDK client init failed, will retry each cycle: %s", exc)

    while True:
        try:
            with SessionLocal() as db:
                result = sync_messages_once(db, client=client)
            logger.info("sync result: %s", result)
        except Exception as exc:
            logger.error("sync cycle error: %s", exc)
        time.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    main()
