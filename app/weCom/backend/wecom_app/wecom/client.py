"""WeComArchiveClient — calls the C SDK via an isolated subprocess.

The WeCom Finance SDK (libWeWorkFinanceSdk_C.so) conflicts with SQLAlchemy's
OpenSSL C extensions when loaded in the same process.  Running the SDK in a
child process (sdk_worker.py) avoids the symbol collision entirely.
"""
import base64
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncResult:
    fetched: int
    processed: int
    message: str


class WeComArchiveClient:
    """Communicates with sdk_worker.py over stdin/stdout JSON lines."""

    def __init__(self) -> None:
        from wecom_app.core.config import get_settings  # lazy import
        settings = get_settings()

        sdk_worker = Path(__file__).parent / "sdk_worker.py"
        env = {
            **os.environ,
            "WECOM_SDK_LIB_DIR": str(settings.wecom_sdk_lib_dir),
            "WECOM_CORP_ID": settings.wecom_corp_id,
            "WECOM_ARCHIVE_SECRET": settings.wecom_archive_secret,
            "WECOM_ARCHIVE_PRIVATE_KEY_PATH": str(settings.wecom_archive_private_key_path),
        }
        self._proc = subprocess.Popen(
            [sys.executable, str(sdk_worker)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            env=env,
            text=True,
        )
        # Wait for the "ready" signal
        ready = self._recv()
        if not ready.get("ready"):
            self._proc.kill()
            raise RuntimeError(f"SDK worker failed to start: {ready.get('error')}")
        logger.info("WeComArchiveClient subprocess ready (pid=%d)", self._proc.pid)

    # ------------------------------------------------------------------

    def _send(self, obj: dict) -> None:
        assert self._proc.stdin
        self._proc.stdin.write(json.dumps(obj) + "\n")
        self._proc.stdin.flush()

    def _recv(self) -> dict:
        assert self._proc.stdout
        line = self._proc.stdout.readline()
        if not line:
            raise RuntimeError("SDK worker process terminated unexpectedly")
        return json.loads(line)

    def _call(self, obj: dict) -> dict:
        self._send(obj)
        result = self._recv()
        if not result.get("ok"):
            raise RuntimeError(result.get("error", "unknown SDK error"))
        return result

    # ------------------------------------------------------------------

    def get_chat_data(self, seq: int, limit: int = 100) -> tuple[list[dict], int]:
        """Returns (messages, max_seq_seen). max_seq advances even when decryption fails."""
        result = self._call({"cmd": "get_chat_data", "seq": seq, "limit": limit})
        return result["data"], result.get("max_seq", 0)

    def download_media(self, sdkfileid: str) -> bytes:
        result = self._call({"cmd": "download_media", "sdkfileid": sdkfileid})
        return base64.b64decode(result["data"])

    def close(self) -> None:
        if self._proc.stdin:
            self._proc.stdin.close()
        self._proc.wait(timeout=5)

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
