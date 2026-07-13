from fastapi import APIRouter, Depends

from wecom_app.core.config import Settings, get_settings
from wecom_app.schemas.archive import HealthOut

router = APIRouter()


@router.get("/health", response_model=HealthOut)
def health(settings: Settings = Depends(get_settings)) -> HealthOut:
    return HealthOut(
        status="ok",
        app_env=settings.app_env,
        sdk_configured=settings.wecom_sdk_lib_dir.exists(),
        private_key_configured=settings.wecom_archive_private_key_path.exists(),
    )
