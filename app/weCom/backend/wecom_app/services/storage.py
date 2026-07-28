from collections.abc import Iterator
from dataclasses import dataclass
from mimetypes import guess_type

from wecom_app.core.config import Settings
from wecom_app.models import Attachment


@dataclass(frozen=True)
class StoredObject:
    chunks: Iterator[bytes]
    content_type: str | None = None
    content_length: int | None = None


class StorageConfigurationError(RuntimeError):
    pass


def build_attachment_storage_key(attachment: Attachment, prefix: str) -> str:
    date_part = attachment.message.msg_time.strftime("%Y/%m/%d")
    suffix = (attachment.file_ext or attachment.attachment_type or "bin").lstrip(".")
    identity = attachment.md5sum or attachment.msgid
    normalized_prefix = prefix.strip().strip("/")
    base = f"{attachment.attachment_type}/{date_part}/{attachment.id}_{identity}.{suffix}"
    return f"{normalized_prefix}/{base}" if normalized_prefix else base


def attachment_content_type(attachment: Attachment, key: str | None = None) -> str | None:
    if attachment.attachment_type == "image":
        suffix = (attachment.file_ext or "").lower().lstrip(".")
        if suffix in {"jpg", "jpeg"}:
            return "image/jpeg"
        if suffix == "png":
            return "image/png"
        if suffix == "gif":
            return "image/gif"
        if suffix == "webp":
            return "image/webp"
        return "image/jpeg"
    if key:
        guessed, _ = guess_type(key)
        return guessed
    return None


class AliyunOssAttachmentStorage:
    backend = "aliyun_oss"

    def __init__(self, settings: Settings):
        if not settings.aliyun_oss_bucket:
            raise StorageConfigurationError("ALIYUN_OSS_BUCKET is required")
        if not settings.aliyun_oss_internal_endpoint:
            raise StorageConfigurationError("ALIYUN_OSS_INTERNAL_ENDPOINT is required")
        if not settings.aliyun_oss_access_key_id or not settings.aliyun_oss_access_key_secret:
            raise StorageConfigurationError("ALIYUN_OSS_ACCESS_KEY_ID/SECRET are required")
        try:
            import oss2
        except ImportError as exc:
            raise StorageConfigurationError("oss2 dependency is required for Aliyun OSS storage") from exc
        endpoint = settings.aliyun_oss_internal_endpoint
        if not endpoint.startswith(("http://", "https://")):
            endpoint = f"https://{endpoint}"
        self.bucket = settings.aliyun_oss_bucket
        self.prefix = settings.aliyun_oss_prefix_normalized
        self._oss_bucket = oss2.Bucket(
            oss2.Auth(settings.aliyun_oss_access_key_id, settings.aliyun_oss_access_key_secret),
            endpoint,
            settings.aliyun_oss_bucket,
            connect_timeout=settings.aliyun_oss_connect_timeout_seconds,
        )

    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> None:
        headers = {"Content-Type": content_type} if content_type else None
        self._oss_bucket.put_object(key, data, headers=headers)

    def open_object(self, key: str) -> StoredObject:
        result = self._oss_bucket.get_object(key)
        headers = getattr(result, "headers", {}) or {}
        content_type = headers.get("Content-Type") or headers.get("content-type")
        content_length_value = headers.get("Content-Length") or headers.get("content-length")
        content_length = int(content_length_value) if content_length_value else None

        def chunks() -> Iterator[bytes]:
            while True:
                chunk = result.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk

        return StoredObject(chunks=chunks(), content_type=content_type, content_length=content_length)


def get_attachment_storage(settings: Settings) -> AliyunOssAttachmentStorage:
    if settings.attachment_storage_backend != "aliyun_oss":
        raise StorageConfigurationError("only ATTACHMENT_STORAGE_BACKEND=aliyun_oss is supported")
    return AliyunOssAttachmentStorage(settings)
