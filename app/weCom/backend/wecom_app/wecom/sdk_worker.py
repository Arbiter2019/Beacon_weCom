"""Standalone script that runs the WeCom Finance SDK in an isolated process.

Called by WeComArchiveClient via subprocess.
Input:  JSON line on stdin  {"cmd": "get_chat_data", "seq": N, "limit": N}
        JSON line on stdin  {"cmd": "download_media", "sdkfileid": "..."}
Output: JSON line on stdout {"ok": true, "data": [...]}
                         or {"ok": false, "error": "..."}
"""
import base64
import ctypes
import json
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding as _padding


# ── ctypes structures ────────────────────────────────────────────────────────

class Slice(ctypes.Structure):
    _fields_ = [("buf", ctypes.c_char_p), ("len", ctypes.c_int)]


class MediaData(ctypes.Structure):
    _fields_ = [
        ("outindexbuf", ctypes.c_char_p),
        ("out_len", ctypes.c_int),
        ("data", ctypes.c_char_p),
        ("data_len", ctypes.c_int),
        ("is_finish", ctypes.c_int),
    ]


def find_so(sdk_dir: str) -> str:
    for p in Path(sdk_dir).rglob("*.so"):
        return str(p)
    raise FileNotFoundError(f"No .so found in {sdk_dir}")


def setup(lib: ctypes.CDLL) -> None:
    lib.NewSdk.restype = ctypes.c_void_p
    lib.NewSdk.argtypes = []
    lib.Init.restype = ctypes.c_int
    lib.Init.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
    lib.DestroySdk.restype = None
    lib.DestroySdk.argtypes = [ctypes.c_void_p]
    lib.NewSlice.restype = ctypes.POINTER(Slice)
    lib.NewSlice.argtypes = []
    lib.FreeSlice.restype = None
    lib.FreeSlice.argtypes = [ctypes.POINTER(Slice)]
    lib.GetChatData.restype = ctypes.c_int
    lib.GetChatData.argtypes = [
        ctypes.c_void_p, ctypes.c_ulonglong, ctypes.c_uint,
        ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(Slice),
    ]
    lib.DecryptData.restype = ctypes.c_int
    lib.DecryptData.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(Slice)]
    lib.NewMediaData.restype = ctypes.POINTER(MediaData)
    lib.NewMediaData.argtypes = []
    lib.FreeMediaData.restype = None
    lib.FreeMediaData.argtypes = [ctypes.POINTER(MediaData)]
    lib.GetMediaData.restype = ctypes.c_int
    lib.GetMediaData.argtypes = [
        ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p,
        ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(MediaData),
    ]


def decrypt_random_key(private_key, encrypt_random_key: str) -> bytes:
    """RSA-PKCS1v15 decrypt encrypt_random_key → raw bytes to pass to DecryptData.

    For ver=1 keys: decrypted bytes are random garbage (wrong key) — callers should
    filter by checking that the result is not obviously garbage (wrong key produces
    inconsistent lengths, while correct decryption produces consistent lengths).
    For ver=2 keys: consistently 88 bytes when correctly decrypted.
    """
    encrypted = base64.b64decode(encrypt_random_key)
    raw = private_key.decrypt(encrypted, _padding.PKCS1v15())
    # Filter obvious garbage from wrong-key decryption: ver=1 messages decrypted
    # with ver=2 key produce varying garbage lengths (< 32 or > 128 bytes typically).
    # ver=2 messages produce a consistent length. Accept anything 32-128 bytes.
    if len(raw) < 32 or len(raw) > 128:
        raise ValueError(f"Decrypted key length {len(raw)} out of expected range [32,128], likely wrong private key version")
    return raw


def main() -> None:
    sdk_dir  = os.environ["WECOM_SDK_LIB_DIR"]
    corpid   = os.environ["WECOM_CORP_ID"]
    secret   = os.environ["WECOM_ARCHIVE_SECRET"]
    key_path = os.environ["WECOM_ARCHIVE_PRIVATE_KEY_PATH"]

    so = find_so(sdk_dir)
    lib = ctypes.CDLL(so)
    setup(lib)

    sdk = lib.NewSdk()
    ret = lib.Init(sdk, corpid.encode(), secret.encode())
    if ret != 0:
        lib.DestroySdk(sdk)
        _reply({"ok": False, "error": f"SDK Init failed code={ret}"})
        return

    with open(key_path, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)

    # signal ready
    _reply({"ok": True, "ready": True})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            cmd = req["cmd"]
            if cmd == "get_chat_data":
                result = _get_chat_data(lib, sdk, private_key, req["seq"], req.get("limit", 100))
                _reply({"ok": True, "data": result["messages"], "max_seq": result["max_seq"]})
            elif cmd == "download_media":
                data = _download_media(lib, sdk, req["sdkfileid"])
                _reply({"ok": True, "data": base64.b64encode(data).decode()})
            else:
                _reply({"ok": False, "error": f"unknown cmd: {cmd}"})
        except Exception as exc:
            _reply({"ok": False, "error": str(exc)})

    lib.DestroySdk(sdk)


def _reply(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _get_chat_data(lib, sdk, private_key, seq: int, limit: int) -> list:
    sl = lib.NewSlice()
    try:
        ret = lib.GetChatData(
            sdk, ctypes.c_ulonglong(seq), ctypes.c_uint(min(limit, 1000)),
            b"", b"", ctypes.c_int(5), sl,
        )
        if ret != 0:
            raise RuntimeError(f"GetChatData error code={ret}")
        buf = sl.contents.buf
        envelope = json.loads(buf.decode("utf-8")) if buf else {}
    finally:
        lib.FreeSlice(sl)

    if envelope.get("errcode", 0) != 0:
        raise RuntimeError(f"GetChatData API error {envelope.get('errcode')}: {envelope.get('errmsg')}")

    messages = []
    max_seq = 0
    for item in envelope.get("chatdata", []):
        seq = item.get("seq", 0)
        if seq > max_seq:
            max_seq = seq
        try:
            encrypt_key = decrypt_random_key(private_key, item["encrypt_random_key"])
        except Exception as exc:
            # ver=1 messages can't be decrypted with our ver=2 key — expected, log at DEBUG only
            print(f"DEBUG skip seq={seq} ver={item.get('publickey_ver')}: {exc}", file=sys.stderr, flush=True)
            continue
        msg_sl = lib.NewSlice()
        try:
            ret2 = lib.DecryptData(
                encrypt_key,          # raw bytes from RSA decryption
                item["encrypt_chat_msg"].encode(), msg_sl,
            )
            if ret2 != 0:
                print(f"DecryptData failed seq={seq} code={ret2}", file=sys.stderr, flush=True)
                continue
            msg_buf = msg_sl.contents.buf
            if msg_buf:
                msg = json.loads(msg_buf.decode("utf-8"))
                msg["seq"] = seq
                messages.append(msg)
        finally:
            lib.FreeSlice(msg_sl)

    return {"messages": messages, "max_seq": max_seq}


def _download_media(lib, sdk, sdkfileid: str) -> bytes:
    chunks: list[bytes] = []
    index = b""
    while True:
        md = lib.NewMediaData()
        try:
            ret = lib.GetMediaData(
                sdk, index, sdkfileid.encode(), b"", b"", ctypes.c_int(5), md,
            )
            if ret != 0:
                raise RuntimeError(f"GetMediaData error code={ret}")
            m = md.contents
            if m.data and m.data_len > 0:
                chunks.append(ctypes.string_at(m.data, m.data_len))
            if m.is_finish:
                break
            index = m.outindexbuf or b""
        finally:
            lib.FreeMediaData(md)
    return b"".join(chunks)


if __name__ == "__main__":
    main()
