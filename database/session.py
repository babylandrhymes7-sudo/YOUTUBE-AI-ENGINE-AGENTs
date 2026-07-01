"""Database session helpers for SQLAlchemy ORM access.

TODO: Keep session creation isolated from repositories and application services.
"""

from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
	"""Create and cache the SQLAlchemy engine for the local PostgreSQL database."""

	if not settings.database_url:
		raise ValueError("DATABASE_URL must be set before creating the database engine.")
	return create_engine(settings.database_url, pool_pre_ping=True, future=True)


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
	"""Create and cache the SQLAlchemy session factory."""

	return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False)


def get_db_session() -> Generator[Session, None, None]:
	"""Yield a SQLAlchemy session for FastAPI dependencies and background jobs."""

	session = get_session_factory()()
	try:
		yield session
	finally:
		session.close()


def initialize_database() -> None:
	"""Create all ORM tables for local development bootstrapping."""

	from .base import Base

	import database.models  # noqa: F401

	Base.metadata.create_all(bind=get_engine())

