from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from wecom_app.core.config import Settings, get_settings
from wecom_app.db.session import get_db
from wecom_app.models import RawEvent
from wecom_app.wecom.callback_crypto import CallbackConfig, CallbackCrypto

router = APIRouter(prefix="/callbacks/wecom")

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
            CallbackConfig(settings.wecom_contact_callback_token, settings.wecom_contact_encoding_aes_key)
        )
    if name in {"customer", "customer-chat"}:
        return CallbackCrypto(
            CallbackConfig(settings.wecom_customer_callback_token, settings.wecom_customer_encoding_aes_key)
        )
    return CallbackCrypto(
        CallbackConfig(settings.wecom_archive_callback_token, settings.wecom_archive_encoding_aes_key)
    )


@router.get("/{callback_name}")
def verify_callback(
    callback_name: str,
    msg_signature: str | None = None,
    timestamp: str = "",
    nonce: str = "",
    echostr: str = "",
    settings: Settings = Depends(get_settings),
) -> str:
    if callback_name not in CALLBACK_SOURCES:
        raise HTTPException(status_code=404, detail="unknown callback")
    crypto = _crypto_for(callback_name, settings)
    if not crypto.verify_signature(msg_signature, timestamp, nonce, echostr):
        raise HTTPException(status_code=403, detail="invalid callback signature")
    return crypto.decrypt_echo(echostr)


@router.post("/{callback_name}")
async def receive_callback(
    callback_name: str,
    request: Request,
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
    if not crypto.verify_signature(msg_signature, timestamp, nonce, body.decode("utf-8", errors="replace")):
        raise HTTPException(status_code=403, detail="invalid callback signature")
    payload = crypto.decrypt_message(body)
    event = RawEvent(
        event_source=CALLBACK_SOURCES[callback_name],
        event_type=payload.get("event_type", callback_name),
        event_key=payload.get("event_key") or f"{callback_name}:{timestamp}:{nonce}:{uuid4()}",
        payload={**payload, "query": dict(request.query_params)},
        process_status="pending",
        received_at=datetime.utcnow(),
    )
    db.add(event)
    db.commit()
    return {"status": "accepted", "event_id": event.id}
