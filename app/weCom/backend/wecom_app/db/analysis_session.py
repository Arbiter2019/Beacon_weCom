from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from wecom_app.core.config import get_settings


analysis_engine = create_engine(get_settings().effective_analysis_database_url, pool_pre_ping=True)
AnalysisSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=analysis_engine)


def get_analysis_db() -> Generator[Session, None, None]:
    db = AnalysisSessionLocal()
    try:
        yield db
    finally:
        db.close()
