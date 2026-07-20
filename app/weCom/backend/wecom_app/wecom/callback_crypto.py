import base64
import hashlib
import struct
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


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
        """Decrypt the AES-encrypted echostr and return the inner msg content."""
        if not self.config.encoding_aes_key:
            return echostr
        # EncodingAESKey is 43 base64 chars; append '=' to make it valid base64 (44 chars = 32 bytes)
        aes_key = base64.b64decode(self.config.encoding_aes_key + "=")
        iv = aes_key[:16]
        ciphertext = base64.b64decode(echostr)
        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        # Remove PKCS7 padding
        pad_len = plaintext[-1]
        plaintext = plaintext[:-pad_len]
        # Plaintext layout: 16-byte random | 4-byte big-endian msg length | msg | corp_id
        (msg_len,) = struct.unpack(">I", plaintext[16:20])
        msg = plaintext[20 : 20 + msg_len]
        return msg.decode("utf-8")

    def decrypt_message(self, body: bytes) -> dict:
        text = body.decode("utf-8", errors="replace")
        return {"raw_xml": text}
