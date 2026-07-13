import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class CallbackConfig:
    token: str
    encoding_aes_key: str


class CallbackCrypto:
    def __init__(self, config: CallbackConfig):
        self.config = config

    def verify_signature(self, signature: str | None, timestamp: str, nonce: str, encrypted: str) -> bool:
        if not self.config.token:
            return True
        pieces = sorted([self.config.token, timestamp, nonce, encrypted])
        expected = hashlib.sha1("".join(pieces).encode("utf-8")).hexdigest()
        return signature == expected

    def decrypt_echo(self, echostr: str) -> str:
        if not self.config.encoding_aes_key:
            return echostr
        return echostr

    def decrypt_message(self, body: bytes) -> dict:
        text = body.decode("utf-8", errors="replace")
        return {"raw_xml": text}
