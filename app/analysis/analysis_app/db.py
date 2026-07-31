from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from analysis_app.config import AnalysisSettings
from analysis_app.models import Base


def create_archive_engine(settings: AnalysisSettings):
    return create_engine(settings.archive_database_url, pool_pre_ping=True)


def create_analysis_engine(settings: AnalysisSettings):
    return create_engine(settings.analysis_database_url, pool_pre_ping=True)


def create_session_makers(settings: AnalysisSettings):
    archive_engine = create_archive_engine(settings)
    analysis_engine = create_analysis_engine(settings)
    archive_session_maker = sessionmaker(autocommit=False, autoflush=False, bind=archive_engine)
    analysis_session_maker = sessionmaker(autocommit=False, autoflush=False, bind=analysis_engine)
    return archive_engine, analysis_engine, archive_session_maker, analysis_session_maker


def initialize_analysis_schema(analysis_engine) -> None:
    Base.metadata.create_all(bind=analysis_engine)

