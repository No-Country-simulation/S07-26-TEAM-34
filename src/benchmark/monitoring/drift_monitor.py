"""
T-06-2: Monitor de percentiles y alertas por saltos entre snapshots.

Compara el snapshot activo con el anterior y genera alertas estructuradas.
Se puede ejecutar como job o llamar desde el panel.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from benchmark.db.repository import SnapshotRepository
from benchmark.domain.models import BenchmarkSnapshot, DimensionId


@dataclass
class PercentileAlert:
    severity: str           # "warning" | "critical"
    dimension: str
    cohort_id: str
    metric: str             # "p50_drift" | "p75_drift" | "n_drop" | "new_cohort_missing"
    current_value: float | None
    previous_value: float | None
    delta: float
    message: str


@dataclass
class DriftMonitorResult:
    checked_at: datetime
    current_snapshot_id: str
    previous_snapshot_id: str | None
    alerts: list[PercentileAlert]
    has_critical: bool
    summary: str


class DriftMonitor:
    """
    Compara distribuciones entre dos snapshots.

    Umbrales configurables:
    - warning_drift:  cambio en p50 que genera advertencia
    - critical_drift: cambio en p50 que genera alerta crítica
    - n_drop_pct:     caída porcentual de n_effective que genera advertencia
    """

    def __init__(
        self,
        warning_drift: float = 0.10,
        critical_drift: float = 0.20,
        n_drop_pct: float = 0.30,
    ) -> None:
        self._warn = warning_drift
        self._crit = critical_drift
        self._n_drop = n_drop_pct

    def check(self, db: Session) -> DriftMonitorResult:
        repo = SnapshotRepository()
        current = repo.get_active_snapshot(db)

        if current is None:
            return DriftMonitorResult(
                checked_at=datetime.utcnow(),
                current_snapshot_id="none",
                previous_snapshot_id=None,
                alerts=[],
                has_critical=False,
                summary="No hay snapshot publicado.",
            )

        # Buscar el snapshot anterior (superseded más reciente)
        from sqlalchemy import select
        from benchmark.db.models import BenchmarkSnapshotRecord
        from benchmark.domain.models import SnapshotStatus

        prev_record = db.scalar(
            select(BenchmarkSnapshotRecord)
            .where(BenchmarkSnapshotRecord.status == SnapshotStatus.SUPERSEDED.value)
            .order_by(BenchmarkSnapshotRecord.published_at.desc())
            .limit(1)
        )

        if prev_record is None:
            return DriftMonitorResult(
                checked_at=datetime.utcnow(),
                current_snapshot_id=current.snapshot_id,
                previous_snapshot_id=None,
                alerts=[],
                has_critical=False,
                summary="Primer snapshot — sin referencia anterior para comparar.",
            )

        from benchmark.db.repository import _record_to_snapshot
        previous = _record_to_snapshot(prev_record)

        alerts = self._compare(current, previous)
        has_critical = any(a.severity == "critical" for a in alerts)

        n_crit = sum(1 for a in alerts if a.severity == "critical")
        n_warn = sum(1 for a in alerts if a.severity == "warning")
        summary = (
            f"Comparación {previous.snapshot_id[:8]}…→{current.snapshot_id[:8]}…: "
            f"{n_crit} alertas críticas, {n_warn} advertencias."
        )

        return DriftMonitorResult(
            checked_at=datetime.utcnow(),
            current_snapshot_id=current.snapshot_id,
            previous_snapshot_id=previous.snapshot_id,
            alerts=alerts,
            has_critical=has_critical,
            summary=summary,
        )

    # ── privados ──────────────────────────────────────────────────────────────

    def _compare(
        self,
        current: BenchmarkSnapshot,
        previous: BenchmarkSnapshot,
    ) -> list[PercentileAlert]:
        alerts: list[PercentileAlert] = []

        prev_index = {
            (d.dimension, d.cohort_id): d
            for d in previous.distributions
        }

        for dist in current.distributions:
            key = (dist.dimension, dist.cohort_id)
            prev = prev_index.get(key)

            if prev is None:
                continue

            # p50 drift
            p50_curr = dist.percentiles.get("p50", 0.0)
            p50_prev = prev.percentiles.get("p50", 0.0)
            delta_p50 = abs(p50_curr - p50_prev)

            if delta_p50 >= self._crit:
                alerts.append(PercentileAlert(
                    severity="critical",
                    dimension=dist.dimension.value,
                    cohort_id=dist.cohort_id,
                    metric="p50_drift",
                    current_value=p50_curr,
                    previous_value=p50_prev,
                    delta=round(delta_p50, 4),
                    message=(
                        f"p50 cambió {delta_p50:.3f} en {dist.dimension.value}/{dist.cohort_id} "
                        f"({p50_prev:.3f}→{p50_curr:.3f}). Requiere revisión antes de publicar."
                    ),
                ))
            elif delta_p50 >= self._warn:
                alerts.append(PercentileAlert(
                    severity="warning",
                    dimension=dist.dimension.value,
                    cohort_id=dist.cohort_id,
                    metric="p50_drift",
                    current_value=p50_curr,
                    previous_value=p50_prev,
                    delta=round(delta_p50, 4),
                    message=(
                        f"p50 cambió {delta_p50:.3f} en {dist.dimension.value}/{dist.cohort_id}."
                    ),
                ))

            # p75 drift
            p75_curr = dist.percentiles.get("p75", 0.0)
            p75_prev = prev.percentiles.get("p75", 0.0)
            delta_p75 = abs(p75_curr - p75_prev)
            if delta_p75 >= self._crit:
                alerts.append(PercentileAlert(
                    severity="critical",
                    dimension=dist.dimension.value,
                    cohort_id=dist.cohort_id,
                    metric="p75_drift",
                    current_value=p75_curr,
                    previous_value=p75_prev,
                    delta=round(delta_p75, 4),
                    message=(
                        f"p75 (umbral top quartile) cambió {delta_p75:.3f} en "
                        f"{dist.dimension.value}/{dist.cohort_id}."
                    ),
                ))

            # Caída de n_effective
            if prev.n_effective > 0:
                drop = (prev.n_effective - dist.n_effective) / prev.n_effective
                if drop >= self._n_drop:
                    alerts.append(PercentileAlert(
                        severity="warning",
                        dimension=dist.dimension.value,
                        cohort_id=dist.cohort_id,
                        metric="n_drop",
                        current_value=float(dist.n_effective),
                        previous_value=float(prev.n_effective),
                        delta=round(drop, 4),
                        message=(
                            f"n_effective cayó {drop:.0%} en "
                            f"{dist.dimension.value}/{dist.cohort_id} "
                            f"({prev.n_effective}→{dist.n_effective})."
                        ),
                    ))

        return alerts
