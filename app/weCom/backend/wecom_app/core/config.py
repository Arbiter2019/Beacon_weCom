from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    api_base_url: str = "http://localhost:8717"
    database_url: str = "sqlite:///./wecom_archive_local.db"

    mysql_host: str = "mysql"
    mysql_port: int = 3306
    mysql_database: str = "wecom_archive"
    mysql_user: str = "wecom"
    mysql_password: str = ""

    wecom_corp_id: str = ""
    wecom_contact_secret: str = ""
    wecom_contact_callback_token: str = ""
    wecom_contact_encoding_aes_key: str = ""
    wecom_customer_api_secret: str = ""
    wecom_customer_secret: str = ""
    wecom_customer_callback_token: str = ""
    wecom_customer_encoding_aes_key: str = ""
    wecom_archive_secret: str = ""
    wecom_archive_callback_token: str = ""
    wecom_archive_encoding_aes_key: str = ""
    wecom_archive_private_key_path: Path = Path("/run/secrets/wecom_archive_private_key.pem")
    wecom_sdk_lib_dir: Path = Path("/opt/wecom_sdk")

    attachment_storage_root: Path = Path("/data/wecom/attachments")
    internal_admin_token: str = Field(default="dev-admin-token")

    worker_poll_interval_seconds: float = 0.01
    message_sync_batch_limit: int = 1000
    message_bootstrap_max_batches: int = 200
    message_sync_newest_first: bool = True

    @property
    def effective_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        )

    @property
    def customer_api_secret(self) -> str:
        return self.wecom_customer_api_secret or self.wecom_customer_secret


@lru_cache
def get_settings() -> Settings:
    return Settings()
