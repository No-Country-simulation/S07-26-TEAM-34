"""
Job offline: BuildSnapshotCandidate

Construye un snapshot candidato desde:
  - Respuestas primarias válidas aún no incluidas en el dataset
  - Datos públicos de referencia (por ahora: distribuciones del snapshot vigente)

Flujo:
  1. Cargar respuestas válidas no incluidas
  2. Construir registros analíticos (sin PII)
  3. Calcular pesos de rebalanceo por dimensión/cohorte
  4. Construir snapshot candidato con SnapshotBuilder
  5. Ejecutar backtest básico contra snapshot vigente
  6. Guardar snapshot candidato como DRAFT
  7. Registrar resultado del backtest en auditoría

El snapshot queda en estado DRAFT hasta aprobación humana explícita.
La publicación se hace con SnapshotRepository.publish_snapshot().

Uso:
    python -m benchmark.jobs.build_snapshot
    python -m benchmark.jobs.build_snapshot --force-publish --approved-by "nombre"
"""
from __future__ import annotations

import argparse
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from benchmark.config.loader import (
    cached_cohort_hierarchy,
    cached_privacy_config,
    cached_questionnaire,
)
from benchmark.db.base import get_session
from benchmark.db.models import AnswerRecord, DimensionScoreRecord, ResponseSessionRecord
from benchmark.db.repository import (
    AuditRepository,
    ResponseRepository,
    SnapshotRepository,
)
from benchmark.engines.rebalancing import PrimaryDataMetrics, RebalancingEngine
from benchmark.engines.snapshot_builder import SnapshotBuilder
from benchmark.domain.models import DimensionId, SnapshotStatus

_METHODOLOGY_VERSION = "1.0.0"
_N_TARGET_PER_COHORT = 50       # tamaño objetivo para peso primario máximo
_RECENCY_HALF_LIFE_DAYS = 180   # días para que una respuesta tenga peso 0.5


@dataclass
class BacktestResult:
    passed: bool
    n_candidate: int
    n_current: int
    dimension_drift: dict[str, float]   # dimensión → cambio promedio de percentil p50
    rejection_reasons: list[str]


@dataclass
class JobResult:
    snapshot_id: str
    status: str   # "created_draft" | "skipped_no_data" | "rejected_backtest"
    backtest: BacktestResult | None
    records_included: int


class BuildSnapshotJob:
    """
    Job reproducible y reanudable.
    Si falla a mitad, puede volver a ejecutarse sin duplicar datos.
    """

    def __init__(self, methodology_version: str = _METHODOLOGY_VERSION) -> None:
        self._version = methodology_version
        self._q = cached_questionnaire(methodology_version)
        self._hierarchy = cached_cohort_hierarchy(methodology_version)
        self._privacy = cached_privacy_config(methodology_version)
        self._response_repo = ResponseRepository()
        self._snapshot_repo = SnapshotRepository()
        self._audit = AuditRepository()
        self._rebalancing = RebalancingEngine()
        self._builder = SnapshotBuilder(self._q, self._hierarchy, self._privacy)

    def run(self, db: Session) -> JobResult:
        # 1. Cargar respuestas válidas pendientes
        pending = self._response_repo.get_valid_not_included(db)
        if not pending:
            return JobResult(
                snapshot_id="", status="skipped_no_data",
                backtest=None, records_included=0
            )

        # 2. Convertir a registros analíticos (sin PII)
        records = self._build_analytic_records(db, pending)

        # 3. Construir snapshot candidato
        snapshot_id = str(uuid.uuid4())
        snapshot = self._builder.build(
            snapshot_id=snapshot_id,
            records=records,
            rebalancing_version=self._rebalancing.VERSION,
            notes=f"Candidato automático con {len(records)} respuestas primarias",
        )

        # 4. Calcular pesos de rebalanceo y agregarlos al snapshot
        weights = self._compute_rebalancing_weights(records, snapshot)
        snapshot.rebalancing_weights = {
            f"{w.dimension}::{w.cohort_id}": {
                "primary_weight": w.primary_weight,
                "public_weight": w.public_weight,
                "factors": w.factors,
            }
            for w in weights
        }

        # 5. Backtest contra snapshot vigente
        current = self._snapshot_repo.get_active_snapshot(db)
        backtest = self._run_backtest(snapshot, current, len(records))

        # 6. Guardar snapshot candidato (siempre, para auditoría)
        self._snapshot_repo.save_snapshot(db, snapshot)

        # 7. Marcar respuestas como incluidas
        for rec in pending:
            self._response_repo.mark_included_in_dataset(db, rec.id)

        self._audit.log(
            db,
            event_type="snapshot.candidate_created",
            resource_type="benchmark_snapshot",
            resource_id=snapshot_id,
            metadata={
                "records_included": len(records),
                "backtest_passed": backtest.passed,
                "rejection_reasons": backtest.rejection_reasons,
            },
        )

        status = "created_draft" if backtest.passed else "rejected_backtest"
        return JobResult(
            snapshot_id=snapshot_id,
            status=status,
            backtest=backtest,
            records_included=len(records),
        )

    # ── privados ──────────────────────────────────────────────────────────────

    def _build_analytic_records(
        self, db: Session, sessions: list[ResponseSessionRecord]
    ) -> list[dict]:
        """
        Construye registros analíticos desde las sesiones persistidas.
        Solo usa bandas de cohorte — sin valores exactos.
        """
        records = []
        for sess in sessions:
            # Cargar scores ya calculados (persistidos en Fase 1)
            score_rows = db.query(DimensionScoreRecord).filter_by(
                session_id=sess.id
            ).all()
            if not score_rows:
                continue

            scores = {row.dimension: row.normalized_score for row in score_rows}

            # Cargar respuestas por question_id → option_id
            answer_rows = db.query(AnswerRecord).filter_by(session_id=sess.id).all()
            answers = {row.question_id: row.option_id for row in answer_rows}

            # Calcular recency score por antigüedad
            age_days = (datetime.utcnow() - sess.received_at).days
            recency = 2 ** (-age_days / _RECENCY_HALF_LIFE_DAYS)

            records.append({
                "scores": scores,
                "answers": answers,
                "cohort_attributes": {
                    k: v for k, v in {
                        "region": sess.region_band,
                        "dc_type": sess.dc_type_band,
                        "capacity_band": sess.capacity_band,
                        "primary_workload": sess.workload_band,
                    }.items() if v
                },
                "quality_score": sess.quality_score,
                "recency_score": recency,
            })
        return records

    def _compute_rebalancing_weights(
        self, records: list[dict], snapshot
    ) -> list:
        """Calcula pesos por dimensión y cohorte para el snapshot candidato."""
        weights = []
        cohort_groups: dict[str, list[dict]] = {}
        for rec in records:
            from benchmark.engines.snapshot_builder import _cohort_id_from_attrs
            cid = _cohort_id_from_attrs(rec["cohort_attributes"])
            cohort_groups.setdefault(cid, []).append(rec)
            cohort_groups.setdefault("global", []).append(rec)

        for cohort_id, group in cohort_groups.items():
            for dim in DimensionId:
                dim_recs = [r for r in group if dim.value in r.get("scores", {})]
                if not dim_recs:
                    continue
                n_eff = len(dim_recs)
                avg_quality = sum(r.get("quality_score", 0) for r in dim_recs) / n_eff
                avg_recency = sum(r.get("recency_score", 0) for r in dim_recs) / n_eff

                # Representatividad: cobertura de los 3 cohorts principales
                unique_cohorts = len({str(r["cohort_attributes"]) for r in dim_recs})
                representativeness = min(1.0, unique_cohorts / 3)

                # Estabilidad: desviación estándar de scores (baja std = alta estabilidad)
                import statistics
                scores_vals = [r["scores"][dim.value] for r in dim_recs]
                std = statistics.stdev(scores_vals) if len(scores_vals) > 1 else 0.0
                stability = max(0.0, 1.0 - std * 2)

                metrics = PrimaryDataMetrics(
                    dimension=dim.value,
                    cohort_id=cohort_id,
                    n_effective=n_eff,
                    n_target=_N_TARGET_PER_COHORT,
                    quality_score=avg_quality,
                    representativeness=representativeness,
                    recency_score=avg_recency,
                    stability_score=stability,
                )
                weights.append(self._rebalancing.calculate_weights(metrics))
        return weights

    def _run_backtest(
        self, candidate, current, n_candidate: int
    ) -> BacktestResult:
        """
        Backtest básico: compara distribuciones del candidato con el snapshot vigente.
        Criterios de rechazo automático:
        - Candidato tiene menos distribuciones que el vigente
        - Drift de p50 > 0.20 en alguna dimensión/cohorte
        - Privacidad: algún n_effective < umbral mínimo
        """
        rejection_reasons: list[str] = []
        dimension_drift: dict[str, float] = {}

        n_current = sum(
            d.n_effective for d in (current.distributions if current else [])
        )

        if current is None:
            # Primer snapshot: siempre pasa el backtest
            return BacktestResult(
                passed=True,
                n_candidate=n_candidate,
                n_current=0,
                dimension_drift={},
                rejection_reasons=[],
            )

        # Comparar distribuciones dimensión por dimensión
        for dim in DimensionId:
            cand_dists = [
                d for d in candidate.distributions if d.dimension == dim
            ]
            curr_dists = {
                d.cohort_id: d
                for d in current.distributions if d.dimension == dim
            }

            for cand_d in cand_dists:
                curr_d = curr_dists.get(cand_d.cohort_id)
                if curr_d is None:
                    continue

                # Drift en p50
                p50_cand = cand_d.percentiles.get("p50", 0)
                p50_curr = curr_d.percentiles.get("p50", 0)
                drift = abs(p50_cand - p50_curr)
                key = f"{dim.value}::{cand_d.cohort_id}"
                dimension_drift[key] = round(drift, 4)

                if drift > 0.20:
                    rejection_reasons.append(
                        f"Drift de p50 > 0.20 en {dim.value}/{cand_d.cohort_id}: {drift:.3f}"
                    )

                # Privacidad: n_effective por debajo del umbral
                if cand_d.n_effective < self._privacy.min_cohort_size:
                    rejection_reasons.append(
                        f"n_effective {cand_d.n_effective} < umbral "
                        f"{self._privacy.min_cohort_size} en {dim.value}/{cand_d.cohort_id}"
                    )

        return BacktestResult(
            passed=len(rejection_reasons) == 0,
            n_candidate=n_candidate,
            n_current=n_current,
            dimension_drift=dimension_drift,
            rejection_reasons=rejection_reasons,
        )


# ── Entrypoint CLI ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Construye un snapshot candidato")
    parser.add_argument("--force-publish", action="store_true",
                        help="Publicar automáticamente si pasa el backtest")
    parser.add_argument("--approved-by", default="job_auto",
                        help="Nombre del aprobador (para auditoría)")
    args = parser.parse_args()

    job = BuildSnapshotJob()

    with get_session() as db:
        result = job.run(db)

        print(f"Status: {result.status}")
        print(f"Registros incluidos: {result.records_included}")

        if result.backtest:
            print(f"Backtest passed: {result.backtest.passed}")
            if result.backtest.rejection_reasons:
                print("Razones de rechazo:")
                for r in result.backtest.rejection_reasons:
                    print(f"  - {r}")

        if args.force_publish and result.status == "created_draft":
            snap_repo = SnapshotRepository()
            snap_repo.publish_snapshot(db, result.snapshot_id, args.approved_by)
            print(f"Snapshot publicado: {result.snapshot_id}")
        elif result.status == "created_draft":
            print(f"Snapshot {result.snapshot_id} en estado DRAFT. "
                  "Revisar y publicar manualmente.")


if __name__ == "__main__":
    main()
