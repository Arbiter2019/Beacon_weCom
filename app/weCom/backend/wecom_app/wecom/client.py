from dataclasses import dataclass


@dataclass(frozen=True)
class SyncResult:
    fetched: int
    processed: int
    message: str


class WeComArchiveClient:
    """Adapter boundary for the Enterprise WeChat Linux SDK.

    The real SDK requires Linux dynamic libraries, private key files, and archive secrets.
    Local development uses this deterministic stub so API, worker, CLI, and UI can be
    tested before those credentials are available.
    """

    def get_chat_data(self, seq: int, limit: int = 100) -> list[dict]:
        return []

    def download_media(self, sdkfileid: str) -> bytes:
        raise RuntimeError("WeCom SDK media download is not configured")
