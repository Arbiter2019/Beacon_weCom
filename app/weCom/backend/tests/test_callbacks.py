import base64
import hashlib
import os
import struct

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from wecom_app.core.config import Settings, get_settings
from wecom_app.models import RawEvent


def _encrypt_wecom_xml(xml: str, encoding_aes_key: str, corp_id: str) -> str:
    aes_key = base64.b64decode(encoding_aes_key + "=")
    payload = (
        os.urandom(16)
        + struct.pack(">I", len(xml.encode("utf-8")))
        + xml.encode("utf-8")
        + corp_id.encode("utf-8")
    )
    pad_len = 32 - (len(payload) % 32)
    payload += bytes([pad_len]) * pad_len
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(aes_key[:16]))
    encryptor = cipher.encryptor()
    return base64.b64encode(encryptor.update(payload) + encryptor.finalize()).decode("utf-8")


def _signature(token: str, timestamp: str, nonce: str, encrypted: str) -> str:
    return hashlib.sha1("".join(sorted([token, timestamp, nonce, encrypted])).encode("utf-8")).hexdigest()


def test_callback_verify_echo(client):
    # Token and AES key are empty in test config, so crypto is bypassed.
    # Response must be plain text (no JSON quotes) per WeCom spec.
    response = client.get("/callbacks/wecom/contact?timestamp=1&nonce=2&echostr=hello")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert response.text == "hello"


def test_callback_post_persists_event(client):
    response = client.post("/callbacks/wecom/archive-event?timestamp=1&nonce=2", content="<xml />")

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_archive_event_callback_triggers_message_sync(client, monkeypatch):
    calls = []

    def fake_sync(db):
        calls.append(db)

    monkeypatch.setattr("wecom_app.api.callbacks.sync_messages_once", fake_sync)

    response = client.post("/callbacks/wecom/archive-event?timestamp=1&nonce=2", content="<xml />")

    assert response.status_code == 200
    assert len(calls) == 1


def test_archive_event_notify_uses_unique_callback_key(client, monkeypatch, db):
    monkeypatch.setattr("wecom_app.api.callbacks.sync_messages_once", lambda db: None)

    for nonce in ["nonce-1", "nonce-2"]:
        response = client.post(
            f"/callbacks/wecom/archive-event?timestamp=1784532141&nonce={nonce}",
            content="<xml><MsgType><![CDATA[event]]></MsgType><Event><![CDATA[msgaudit_notify]]></Event></xml>",
        )
        assert response.status_code == 200

    from wecom_app.models import RawEvent

    events = db.query(RawEvent).filter(RawEvent.event_type == "msgaudit_notify").all()
    assert len(events) == 2
    assert len({event.event_key for event in events}) == 2


def test_encrypted_callback_post_uses_encrypt_field_for_signature(client, db):
    token = "customer-token"
    aes_key = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"
    corp_id = "wwtestcorp"
    get_settings.cache_clear()
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        wecom_corp_id=corp_id,
        wecom_customer_callback_token=token,
        wecom_customer_encoding_aes_key=aes_key,
    )

    encrypted = _encrypt_wecom_xml(
        "<xml><ToUserName><![CDATA[wwtestcorp]]></ToUserName>"
        "<FromUserName><![CDATA[external_user]]></FromUserName>"
        "<CreateTime>1784530639</CreateTime>"
        "<MsgType><![CDATA[event]]></MsgType>"
        "<Event><![CDATA[change_external_contact]]></Event>"
        "<ChangeType><![CDATA[add_external_contact]]></ChangeType>"
        "<UserID><![CDATA[XuWei]]></UserID>"
        "<ExternalUserID><![CDATA[wm_external]]></ExternalUserID></xml>",
        aes_key,
        corp_id,
    )
    timestamp = "1784530639"
    nonce = "1784469198"
    signature = _signature(token, timestamp, nonce, encrypted)
    body = f"<xml><ToUserName><![CDATA[{corp_id}]]></ToUserName><Encrypt><![CDATA[{encrypted}]]></Encrypt></xml>"

    response = client.post(
        f"/callbacks/wecom/customer?msg_signature={signature}&timestamp={timestamp}&nonce={nonce}",
        content=body,
    )

    assert response.status_code == 200
    event = db.query(RawEvent).order_by(RawEvent.id.desc()).first()
    assert event.event_source == "contact"
    assert event.event_type == "change_external_contact"
    assert event.event_key == "customer:change_external_contact:add_external_contact:XuWei:wm_external"
    assert event.payload["ChangeType"] == "add_external_contact"
    assert event.payload["UserID"] == "XuWei"
    assert event.payload["ExternalUserID"] == "wm_external"
