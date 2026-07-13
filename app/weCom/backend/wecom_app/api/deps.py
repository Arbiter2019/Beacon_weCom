from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from wecom_app.core.config import Settings, get_settings
from wecom_app.db.session import get_db
from wecom_app.models import ObservableEmployeeScope


def require_admin(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> str:
    expected = f"Bearer {settings.internal_admin_token}"
    if not authorization or authorization != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin token")
    return "internal_admin"


def require_observable_userid(userid: str, db: Session = Depends(get_db)) -> str:
    scope = db.scalar(
        select(ObservableEmployeeScope).where(
            ObservableEmployeeScope.userid == userid,
            ObservableEmployeeScope.scope_status == "enabled",
        )
    )
    if scope is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="userid not observable")
    return userid
