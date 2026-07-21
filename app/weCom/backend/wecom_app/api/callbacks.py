from datetime import datetime
import logging
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from wecom_app.core.config import Settings, get_settings
from wecom_app.db.session import SessionLocal, get_db
from wecom_app.models import RawEvent
from wecom_app.services.sync_jobs import sync_messages_once
from wecom_app.wecom.callback_crypto import CallbackConfig, CallbackCrypto

router = APIRouter(prefix="/callbacks/wecom")
logger = logging.getLogger(__name__)

CALLBACK_SOURCES = {
    "contact": "contact",
    "customer": "contact",
    "customer-chat": "customer_chat",
    "archive-consent": "archive_consent",
    "archive-event": "archive_event",
}


def _crypto_for(name: str, settings: Settings) -> CallbackCrypto:
    if name == "contact":
        return CallbackCrypto(
            CallbackConfig(
                settings.wecom_contact_callback_token,
                settings.wecom_contact_encoding_aes_key,
                settings.wecom_corp_id,
            )
        )
    if name in {"customer", "customer-chat"}:
        return CallbackCrypto(
            CallbackConfig(
                settings.wecom_customer_callback_token,
                settings.wecom_customer_encoding_aes_key,
                settings.wecom_corp_id,
            )
        )
    return CallbackCrypto(
        CallbackConfig(
            settings.wecom_archive_callback_token,
            settings.wecom_archive_encoding_aes_key,
            settings.wecom_corp_id,
        )
    )


def _sync_messages_after_archive_event() -> None:
    try:
        with SessionLocal() as db:
            sync_messages_once(db)
    except Exception as exc:
        logger.error("archive event triggered message sync failed: %s", exc)


@router.get("/{callback_name}")
def verify_callback(
    callback_name: str,
    msg_signature: str | None = None,
    timestamp: str = "",
    nonce: str = "",
    echostr: str = "",
    settings: Settings = Depends(get_settings),
) -> Response:
    if callback_name not in CALLBACK_SOURCES:
        raise HTTPException(status_code=404, detail="unknown callback")
    crypto = _crypto_for(callback_name, settings)
    if not crypto.verify_signature(msg_signature, timestamp, nonce, echostr):
        raise HTTPException(status_code=403, detail="invalid callback signature")
    # WeCom requires plain text response — no JSON encoding, no quotes, no BOM
    return Response(content=crypto.decrypt_echo(echostr), media_type="text/plain")


@router.post("/{callback_name}")
async def receive_callback(
    callback_name: str,
    request: Request,
    background_tasks: BackgroundTasks,
    msg_signature: str | None = None,
    timestamp: str = "",
    nonce: str = "",
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    if callback_name not in CALLBACK_SOURCES:
        raise HTTPException(status_code=404, detail="unknown callback")
    body = await request.body()
    crypto = _crypto_for(callback_name, settings)
    encrypted = crypto.extract_encrypt(body)
    if not crypto.verify_signature(msg_signature, timestamp, nonce, encrypted):
        raise HTTPException(status_code=403, detail="invalid callback signature")
    try:
        payload = crypto.decrypt_message(body)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    event = RawEvent(
        event_source=CALLBACK_SOURCES[callback_name],
        event_type=payload.get("event_type", callback_name),
        event_key=(
            f"{callback_name}:{payload['event_key']}"
            if payload.get("event_key")
            else f"{callback_name}:{timestamp}:{nonce}:{uuid4()}"
        ),
        payload={**payload, "query": dict(request.query_params)},
        process_status="pending",
        received_at=datetime.utcnow(),
    )
    db.add(event)
    db.commit()
    if callback_name == "archive-event":
        background_tasks.add_task(_sync_messages_after_archive_event)
    return {"status": "accepted", "event_id": event.id}
