"""
Configuración de SQLAlchemy y sesión.

Soporta PostgreSQL (producción) y SQLite (desarrollo/tests).
La URL se controla con la variable de entorno DATABASE_URL.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///./benchmark_dev.db",
)

# Para SQLite: habilitar foreign keys (desactivadas por defecto)
_engine = create_engine(
    _DATABASE_URL,
    connect_args={"check_same_thread": False} if _DATABASE_URL.startswith("sqlite") else {},
    echo=False,
)

if _DATABASE_URL.startswith("sqlite"):
    @event.listens_for(_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_engine():
    return _engine


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager para sesiones de DB. Hace rollback en excepción."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
