"""
T-06-1: Panel interno de calidad del dataset, crecimiento y drift entre fuentes.

Calcula métricas desde la DB sin exponer datos individuales.
Solo accesible desde endpoints admin (no públicos).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from benchmark.db.models import (
    AuditEventRecord,
    BenchmarkSnapshotRecord,
    DimensionScoreRecord,
    OperatorResultRecord,
    ResponseSessionRecord,
)
from benchmark.domain.models import DimensionId, SnapshotStatus


@dataclass
class DimensionQuality:
    dimension: str
    n_responses: int
    mean_score: float
    std_score: float
    mean_quality: float   # quality_score promedio de las sesiones


@dataclass
class GrowthMetrics:
    total_valid: int
    total_rejected: int
    acceptance_rate: float
    new_last_7d: int
    new_last_30d: int
    included_in_dataset: int
    pending_inclusion: int


@dataclass
class SnapshotDriftSummary:
    current_snapshot_id: str | None
    previous_snapshot_id: str | None
    drift_by_dimension: dict[str, float]   # dimensión::cohort → Δp50
    max_drift: float
    alert: bool                            # True si algún drift > umbral


@dataclass
class DashboardReport:
    generated_at: datetime
    growth: GrowthMetrics
    dimension_quality: list[DimensionQuality]
    snapshot_drift: SnapshotDriftSummary
    audit_summary: dict[str, int]          # event_type → count últimas 24h


class DashboardService:
    """
    Agrega métricas del sistema para el panel interno.
    No expone respuestas individuales — solo estadísticas agregadas.
    """

    DRIFT_ALERT_THRESHOLD = 0.15

    def get_report(self, db: Session) -> DashboardReport:
        now = datetime.utcnow()
        return DashboardReport(
            generated_at=now,
            growth=self._growth_metrics(db, now),
            dimension_quality=self._dimension_quality(db),
            snapshot_drift=self._snapshot_drift(db),
            audit_summary=self._audit_summary(db, now),
        )

    # ── privados ──────────────────────────────────────────────────────────────

    def _growth_metrics(self, db: Session, now: datetime) -> GrowthMetrics:
        total_valid = db.scalar(
            select(func.count()).where(
                ResponseSessionRecord.validation_status == "valid"
            )
        ) or 0
        total_rejected = db.scalar(
            select(func.count()).where(
                ResponseSessionRecord.validation_status == "rejected"
            )
        ) or 0
        total = total_valid + total_rejected
        acceptance_rate = total_valid / total if total > 0 else 0.0

        new_7d = db.scalar(
            select(func.count()).where(
                ResponseSessionRecord.received_at >= now - timedelta(days=7)
            )
        ) or 0
        new_30d = db.scalar(
            select(func.count()).where(
                ResponseSessionRecord.received_at >= now - timedelta(days=30)
            )
        ) or 0
        included = db.scalar(
            select(func.count()).where(
                ResponseSessionRecord.included_in_dataset == True  # noqa: E712
            )
        ) or 0
        pending = db.scalar(
            select(func.count()).where(
                ResponseSessionRecord.validation_status == "valid",
                ResponseSessionRecord.included_in_dataset == False,  # noqa: E712
            )
        ) or 0

        return GrowthMetrics(
            total_valid=total_valid,
            total_rejected=total_rejected,
            acceptance_rate=round(acceptance_rate, 3),
            new_last_7d=new_7d,
            new_last_30d=new_30d,
            included_in_dataset=included,
            pending_inclusion=pending,
        )

    def _dimension_quality(self, db: Session) -> list[DimensionQuality]:
        results = []
        for dim in DimensionId:
            # Calcular mean y n en una consulta
            row = db.execute(
                select(
                    func.count(DimensionScoreRecord.id).label("n"),
                    func.avg(DimensionScoreRecord.normalized_score).label("mean"),
                ).where(DimensionScoreRecord.dimension == dim.value)
            ).one()

            n = row.n or 0
            mean = row.mean or 0.0

            # Calcular std manualmente (SQLite no soporta window functions en este contexto)
            std = 0.0
            if n > 1:
                scores = [
                    r[0] for r in db.execute(
                        select(DimensionScoreRecord.normalized_score)
                        .where(DimensionScoreRecord.dimension == dim.value)
                    ).all()
                ]
                variance = sum((s - mean) ** 2 for s in scores) / len(scores)
                std = variance ** 0.5

            # quality_score promedio de sesiones con scores en esta dimensión
            mean_quality = db.scalar(
                select(func.avg(ResponseSessionRecord.quality_score))
                .join(DimensionScoreRecord,
                      DimensionScoreRecord.session_id == ResponseSessionRecord.id)
                .where(DimensionScoreRecord.dimension == dim.value)
            ) or 0.0

            results.append(DimensionQuality(
                dimension=dim.value,
                n_responses=n,
                mean_score=round(mean, 4),
                std_score=round(std, 4),
                mean_quality=round(mean_quality, 4),
            ))
        return results

    def _snapshot_drift(self, db: Session) -> SnapshotDriftSummary:
        # Obtener los dos snapshots publicados más recientes
        snapshots = db.scalars(
            select(BenchmarkSnapshotRecord)
            .where(BenchmarkSnapshotRecord.status == SnapshotStatus.PUBLISHED.value)
            .order_by(BenchmarkSnapshotRecord.published_at.desc())
            .limit(2)
        ).all()

        if len(snapshots) < 2:
            return SnapshotDriftSummary(
                current_snapshot_id=snapshots[0].id if snapshots else None,
                previous_snapshot_id=None,
                drift_by_dimension={},
                max_drift=0.0,
                alert=False,
            )

        current, previous = snapshots[0], snapshots[1]
        curr_dists = current.distributions_json
        prev_dists = previous.distributions_json

        drift_by_dim: dict[str, float] = {}
        for key, curr_d in curr_dists.items():
            prev_d = prev_dists.get(key)
            if prev_d is None:
                continue
            delta = abs(
                curr_d["percentiles"].get("p50", 0) -
                prev_d["percentiles"].get("p50", 0)
            )
            drift_by_dim[key] = round(delta, 4)

        max_drift = max(drift_by_dim.values(), default=0.0)

        return SnapshotDriftSummary(
            current_snapshot_id=current.id,
            previous_snapshot_id=previous.id,
            drift_by_dimension=drift_by_dim,
            max_drift=round(max_drift, 4),
            alert=max_drift > self.DRIFT_ALERT_THRESHOLD,
        )

    def _audit_summary(self, db: Session, now: datetime) -> dict[str, int]:
        rows = db.execute(
            select(
                AuditEventRecord.event_type,
                func.count(AuditEventRecord.id).label("n"),
            )
            .where(AuditEventRecord.occurred_at >= now - timedelta(hours=24))
            .group_by(AuditEventRecord.event_type)
        ).all()
        return {r.event_type: r.n for r in rows}
