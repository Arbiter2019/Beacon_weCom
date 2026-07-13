import time

from wecom_app.core.config import get_settings
from wecom_app.db.session import SessionLocal
from wecom_app.services.sync_jobs import sync_messages_once


def run_once(task_type: str = "message") -> dict:
    with SessionLocal() as db:
        if task_type == "message":
            result = sync_messages_once(db)
            return {"task": task_type, **result.__dict__}
        if task_type in {"contacts", "customer-chat"}:
            return {"task": task_type, "fetched": 0, "processed": 0, "message": "stub task completed"}
        raise ValueError(f"unsupported sync task: {task_type}")


def main() -> None:
    settings = get_settings()
    while True:
        run_once("message")
        time.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    main()
