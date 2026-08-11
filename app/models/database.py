"""
Conexión a la base de datos.

Usa DATABASE_URL del entorno. Default: SQLite para desarrollo local.
En producción: postgresql://user:pass@host/dbname (Neon).
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./benchmark.db")

_engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    # Neon (y otros Postgres serverless) cierran conexiones ociosas del lado del server.
    # Sin esto, la primera query tras un rato de inactividad falla con
    # "SSL connection has been closed unexpectedly" en vez de reconectar.
    pool_pre_ping=True,
    pool_recycle=300,
)

# SQLite: activar foreign keys (desactivadas por defecto)
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(_engine, "connect")
    def _fk_pragma(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def create_tables() -> None:
    """Crea las tablas si no existen. Sin migraciones — suficiente para este esquema."""
    Base.metadata.create_all(_engine)


def get_engine():
    return _engine


@contextmanager
def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
