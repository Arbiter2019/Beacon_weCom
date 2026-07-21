import base64
import hashlib
import struct
from dataclasses import dataclass
from xml.etree import ElementTree

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


@dataclass(frozen=True)
class CallbackConfig:
    token: str
    encoding_aes_key: str
    corp_id: str = ""


class CallbackCrypto:
    def __init__(self, config: CallbackConfig):
        self.config = config

    def verify_signature(self, signature: str | None, timestamp: str, nonce: str, encrypted: str) -> bool:
        if not self.config.token:
            return True
        pieces = sorted([self.config.token, timestamp, nonce, encrypted])
        expected = hashlib.sha1("".join(pieces).encode("utf-8")).hexdigest()
        return signature == expected

    @staticmethod
    def extract_encrypt(body: bytes) -> str:
        text = body.decode("utf-8", errors="replace")
        try:
            root = ElementTree.fromstring(text)
        except ElementTree.ParseError:
            return text
        encrypt = root.findtext("Encrypt")
        return encrypt or text

    def decrypt_echo(self, echostr: str) -> str:
        """Decrypt the AES-encrypted echostr and return the inner msg content."""
        if not self.config.encoding_aes_key:
            return echostr
        return self._decrypt_text(echostr)

    def _decrypt_text(self, encrypted: str) -> str:
        # EncodingAESKey is 43 base64 chars; append '=' to make it valid base64 (44 chars = 32 bytes)
        aes_key = base64.b64decode(self.config.encoding_aes_key + "=")
        iv = aes_key[:16]
        ciphertext = base64.b64decode(encrypted)
        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        # Remove PKCS7 padding
        pad_len = plaintext[-1]
        plaintext = plaintext[:-pad_len]
        # Plaintext layout: 16-byte random | 4-byte big-endian msg length | msg | corp_id
        (msg_len,) = struct.unpack(">I", plaintext[16:20])
        msg = plaintext[20 : 20 + msg_len]
        corp_id = plaintext[20 + msg_len :].decode("utf-8", errors="replace")
        if self.config.corp_id and corp_id != self.config.corp_id:
            raise ValueError("callback corp_id mismatch")
        return msg.decode("utf-8")

    def decrypt_message(self, body: bytes) -> dict:
        if not self.config.encoding_aes_key:
            text = body.decode("utf-8", errors="replace")
        else:
            text = self._decrypt_text(self.extract_encrypt(body))
        payload = self.parse_xml(text)
        payload["raw_xml"] = text
        event = payload.get("Event") or payload.get("MsgType")
        if event:
            payload["event_type"] = event
        event_key_parts = [
            payload.get("Event") or payload.get("MsgType"),
            payload.get("ChangeType"),
            payload.get("UserID"),
            payload.get("ExternalUserID") or payload.get("ChatId"),
        ]
        if event_key_parts[0] and any(event_key_parts[1:]):
            payload["event_key"] = ":".join(part for part in event_key_parts if part)
        return payload

    @staticmethod
    def parse_xml(text: str) -> dict:
        try:
            root = ElementTree.fromstring(text)
        except ElementTree.ParseError:
            return {}
        return {child.tag: child.text or "" for child in root}
