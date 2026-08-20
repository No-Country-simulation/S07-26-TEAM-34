"""
Tablas de la base de datos — exactamente las 3 definidas en el backlog (sección 11).

operators        → una fila por cuestionario completado (sintético o real)
dimension_scores → una fila por operador y por dimensión (5 filas por operador)
results          → una fila por operador con el resultado ya calculado

Sin tablas extra. Sin auditoría. Sin ContactStore. Sin snapshots.
El dataset agregado se calcula con SQL sobre dimension_scores filtrando por source.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    Text,
    event as sa_event,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from sqlalchemy.types import JSON

from app.models.database import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class SourceEnum(str, enum.Enum):
    public_synthetic = "public_synthetic"
    primary = "primary"


class DimensionEnum(str, enum.Enum):
    visibilidad = "visibilidad"
    atribucion_friccion = "atribucion_friccion"
    latencia = "latencia"
    auto_cuantificacion = "auto_cuantificacion"
    bloqueantes = "bloqueantes"


# ── Tipo JSON compatible con SQLite y PostgreSQL ──────────────────────────────
# PostgreSQL usa JSONB nativo; SQLite usa JSON genérico.
# Se elige en runtime según el driver.

import os
_DB_URL = os.environ.get("DATABASE_URL", "sqlite")
_JsonType = JSONB if "postgresql" in _DB_URL else JSON


# ── Tabla 1: operators ────────────────────────────────────────────────────────

class Operator(Base):
    """
    Una fila por cuestionario completado, sintético o real.
    El ID es aleatorio (UUID) — sin relación con nombre, email o empresa.
    No capturamos PII: el formulario no lo pide.
    """
    __tablename__ = "operators"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source: Mapped[SourceEnum] = mapped_column(
        Enum(SourceEnum, name="source_enum"), nullable=False
    )
    region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    facility_size: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dc_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    benchmark_version: Mapped[str] = mapped_column(String(20), nullable=False)
    dimension_version: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    scores: Mapped[list["DimensionScore"]] = relationship(
        back_populates="operator", cascade="all, delete-orphan"
    )
    result: Mapped["Result | None"] = relationship(
        back_populates="operator", uselist=False, cascade="all, delete-orphan"
    )

    @validates("source")
    def validate_source(self, key, value):
        return SourceEnum(value)  # lanza ValueError si el valor no es válido


# ── Tabla 2: dimension_scores ─────────────────────────────────────────────────

class DimensionScore(Base):
    """
    Una fila por operador y por dimensión → 5 filas por operador.
    Guarda el score normalizado (0-100) y las respuestas crudas.
    Las respuestas crudas permiten recalibrar en el futuro sin perder información (doc §2.5).
    """
    __tablename__ = "dimension_scores"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    operator_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("operators.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    dimension: Mapped[DimensionEnum] = mapped_column(
        Enum(DimensionEnum, name="dimension_enum"), nullable=False
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)          # 0-100
    raw_answers: Mapped[dict] = mapped_column(_JsonType, nullable=False)  # valores crudos

    operator: Mapped["Operator"] = relationship(back_populates="scores")

    @validates("dimension")
    def validate_dimension(self, key, value):
        return DimensionEnum(value)  # lanza ValueError si el valor no es válido

    __table_args__ = (
        # Un operador tiene exactamente un score por dimensión
        __import__("sqlalchemy").UniqueConstraint(
            "operator_id", "dimension", name="uq_score_per_dimension"
        ),
    )


# ── Tabla 3: results ──────────────────────────────────────────────────────────

class Result(Base):
    """
    Una fila por operador con el resultado ya calculado.
    Es lo que consumen el endpoint de resultados y el de PDF,
    evitando recalcular todo cada vez que alguien pide su reporte.
    """
    __tablename__ = "results"

    operator_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("operators.id", ondelete="CASCADE"),
        primary_key=True
    )
    percentiles: Mapped[dict] = mapped_column(_JsonType, nullable=False)
    friccion_principal: Mapped[str] = mapped_column(Text, nullable=False)
    profile: Mapped[str] = mapped_column(Text, nullable=False)
    top_quartile_gaps: Mapped[dict] = mapped_column(_JsonType, nullable=False)
    diagnostico_texto: Mapped[str] = mapped_column(Text, nullable=False)
    # {"titular": str, "accion_sugerida": str, "confianza_nivel": str, "confianza_descripcion": str}
    # Nullable: filas creadas antes de esta columna no lo tienen.
    diagnostico_meta: Mapped[dict | None] = mapped_column(_JsonType, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    operator: Mapped["Operator"] = relationship(back_populates="result")
