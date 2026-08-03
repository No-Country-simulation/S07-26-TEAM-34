"""
Modelos ORM — cinco zonas de datos con fronteras duras. (ADR-004)

Zona 1 — Contacto opcional   : ContactStore (tabla separada, retención limitada)
Zona 2 — Respuestas pseudónimas: ResponseSession, Answer
Zona 3 — Analítica           : DimensionScoreRecord, CohortAssignmentRecord
Zona 4 — Agregada            : AggregateMetricRecord (solo vía jobs offline)
Zona 5 — Publicación         : BenchmarkSnapshotRecord, OperatorResultRecord

REGLAS:
- ContactStore no tiene FK hacia ninguna tabla analítica.
- Ninguna tabla analítica guarda nombre, email, empresa ni localización exacta.
- Los cuasi-identificadores (capacidad, edad) ya llegaron como bandas desde la API.
- AuditEventRecord registra accesos administrativos y cambios de metodología.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from benchmark.db.base import Base


# ── ZONA 1: Contacto opcional ─────────────────────────────────────────────────

class ContactStore(Base):
    """
    Almacén de contacto separado. NO tiene FK hacia tablas analíticas.

    Propósito único: entregar el PDF al operador.
    Se elimina al vencer la retención sin afectar el dataset anónimo.
    """
    __tablename__ = "contact_store"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # response_id es una referencia lógica, no una FK — la relación no se puede reconstruir
    # desde el dominio analítico
    response_id_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    encrypted_email: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# ── ZONA 2: Respuestas pseudónimas ────────────────────────────────────────────

class ResponseSessionRecord(Base):
    """
    Sesión de respuesta pseudónima. El ID es aleatorio (UUID), no derivado de datos del operador.
    """
    __tablename__ = "response_sessions"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_response_idempotency"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)   # UUID aleatorio
    questionnaire_version: Mapped[str] = mapped_column(String(20), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Atributos de cohorte en BANDAS — nunca valores exactos
    region_band: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dc_type_band: Mapped[str | None] = mapped_column(String(32), nullable=True)
    capacity_band: Mapped[str | None] = mapped_column(String(32), nullable=True)
    workload_band: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Estado en el pipeline
    validation_status: Mapped[str] = mapped_column(String(16), nullable=False)  # valid / rejected
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    included_in_dataset: Mapped[bool] = mapped_column(Boolean, default=False)

    answers: Mapped[list["AnswerRecord"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    dimension_scores: Mapped[list["DimensionScoreRecord"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    cohort_assignment: Mapped["CohortAssignmentRecord | None"] = relationship(
        back_populates="session", uselist=False, cascade="all, delete-orphan"
    )
    result: Mapped["OperatorResultRecord | None"] = relationship(
        back_populates="session", uselist=False, cascade="all, delete-orphan"
    )


class AnswerRecord(Base):
    """Respuesta individual por pregunta. Sin texto libre que pueda identificar."""
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("response_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[str] = mapped_column(String(64), nullable=False)
    option_id: Mapped[str] = mapped_column(String(64), nullable=False)

    session: Mapped["ResponseSessionRecord"] = relationship(back_populates="answers")

    __table_args__ = (
        UniqueConstraint("session_id", "question_id", name="uq_answer_per_question"),
        Index("ix_answers_session_question", "session_id", "question_id"),
    )


# ── ZONA 3: Analítica ─────────────────────────────────────────────────────────

class DimensionScoreRecord(Base):
    """Score por dimensión. Sin datos individuales identificables."""
    __tablename__ = "dimension_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("response_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dimension: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_score: Mapped[float] = mapped_column(Float, nullable=False)
    normalized_score: Mapped[float] = mapped_column(Float, nullable=False)
    max_possible: Mapped[float] = mapped_column(Float, nullable=False)
    scoring_version: Mapped[str] = mapped_column(String(20), nullable=False)
    blocker_types: Mapped[list] = mapped_column(JSON, default=list)
    evidence: Mapped[list] = mapped_column(JSON, default=list)  # lista de AnswerEvidence

    session: Mapped["ResponseSessionRecord"] = relationship(back_populates="dimension_scores")

    __table_args__ = (
        UniqueConstraint("session_id", "dimension", name="uq_score_per_dimension"),
    )


class CohortAssignmentRecord(Base):
    """Cohorte asignada con fallback. Sin identificadores directos."""
    __tablename__ = "cohort_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("response_sessions.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True
    )
    cohort_id: Mapped[str] = mapped_column(String(256), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    level_label: Mapped[str] = mapped_column(String(128), nullable=False)
    attributes_used: Mapped[dict] = mapped_column(JSON, default=dict)
    fallback_path: Mapped[list] = mapped_column(JSON, default=list)
    effective_n: Mapped[int] = mapped_column(Integer, nullable=False)
    cohort_version: Mapped[str] = mapped_column(String(20), nullable=False)
    privacy_suppressed: Mapped[bool] = mapped_column(Boolean, default=False)

    session: Mapped["ResponseSessionRecord"] = relationship(back_populates="cohort_assignment")


# ── ZONA 4: Agregada ──────────────────────────────────────────────────────────

class AggregateMetricRecord(Base):
    """
    Métricas agregadas aprobadas para uso analítico.
    Solo se crean mediante jobs offline controlados — nunca por consultas ad hoc.
    """
    __tablename__ = "aggregate_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("benchmark_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    dimension: Mapped[str] = mapped_column(String(64), nullable=False)
    cohort_id: Mapped[str] = mapped_column(String(256), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    n_bruto: Mapped[int] = mapped_column(Integer, nullable=False)
    n_effective: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[str] = mapped_column(String(64), nullable=False)
    privacy_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    approval_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/approved/rejected
    metrics_json: Mapped[dict] = mapped_column(JSON, nullable=False)  # percentiles, mean, std, etc.
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    snapshot: Mapped["BenchmarkSnapshotRecord"] = relationship(back_populates="aggregate_metrics")


# ── ZONA 5: Publicación ───────────────────────────────────────────────────────

class BenchmarkSnapshotRecord(Base):
    """
    Snapshot publicado e inmutable. Una vez status=published no se modifica.
    Cualquier corrección produce un nuevo snapshot.
    """
    __tablename__ = "benchmark_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # draft/published/superseded
    questionnaire_version: Mapped[str] = mapped_column(String(20), nullable=False)
    scoring_version: Mapped[str] = mapped_column(String(20), nullable=False)
    cohort_version: Mapped[str] = mapped_column(String(20), nullable=False)
    rebalancing_version: Mapped[str] = mapped_column(String(20), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    primary_data_cutoff: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    distributions_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    top_quartile_practices_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    rebalancing_weights_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    privacy_thresholds_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    methodology_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    approved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)

    aggregate_metrics: Mapped[list["AggregateMetricRecord"]] = relationship(
        back_populates="snapshot"
    )
    results: Mapped[list["OperatorResultRecord"]] = relationship(back_populates="snapshot")


class OperatorResultRecord(Base):
    """Resultado generado para un operador. Inmutable — nunca se recalcula."""
    __tablename__ = "operator_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("response_sessions.id", ondelete="RESTRICT"),
        nullable=False, index=True
    )
    snapshot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("benchmark_snapshots.id", ondelete="RESTRICT"),
        nullable=False
    )
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    questionnaire_version: Mapped[str] = mapped_column(String(20), nullable=False)
    scoring_version: Mapped[str] = mapped_column(String(20), nullable=False)
    cohort_version: Mapped[str] = mapped_column(String(20), nullable=False)
    rebalancing_version: Mapped[str] = mapped_column(String(20), nullable=False)
    report_json: Mapped[dict] = mapped_column(JSON, nullable=False)  # OperatorReport serializado

    session: Mapped["ResponseSessionRecord"] = relationship(back_populates="result")
    snapshot: Mapped["BenchmarkSnapshotRecord"] = relationship(back_populates="results")


# ── Auditoría ─────────────────────────────────────────────────────────────────

class AuditEventRecord(Base):
    """
    Registro de accesos administrativos, exportaciones y cambios de metodología.
    No guarda respuestas completas.
    """
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
