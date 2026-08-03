"""
Seed del snapshot inicial para desarrollo.

Crea un BenchmarkSnapshot publicado con distribuciones sintéticas basadas
en el cuestionario v1.0.0. Sin datos reales de operadores.

Uso:
    python -m benchmark.db.seed
"""
from __future__ import annotations

import uuid
from datetime import datetime

from benchmark.config.loader import cached_cohort_hierarchy, cached_privacy_config, cached_questionnaire
from benchmark.db.base import get_session
from benchmark.db.models import Base
from benchmark.db.repository import SnapshotRepository
from benchmark.engines.snapshot_builder import SnapshotBuilder
from benchmark.domain.models import DimensionId, SnapshotStatus


def _synthetic_records(n: int = 50) -> list[dict]:
    """
    Genera n registros sintéticos con distribución uniforme de scores.
    No son datos reales — solo para poblar el snapshot de desarrollo.
    """
    import random
    random.seed(42)
    q = cached_questionnaire("1.0.0")
    cohorts = [
        {"region": "latam",   "dc_type": "colo",       "capacity_band": "medium", "primary_workload": "general"},
        {"region": "europe",  "dc_type": "enterprise",  "capacity_band": "large",  "primary_workload": "hpc"},
        {"region": "northam", "dc_type": "hyperscale",  "capacity_band": "xlarge", "primary_workload": "mixed"},
    ]
    records = []
    for i in range(n):
        cohort = cohorts[i % len(cohorts)]
        answers = {}
        scores: dict[str, float] = {}
        for dim in DimensionId:
            dim_questions = q.questions_for_dimension(dim)
            raw = 0.0
            max_p = 0.0
            for question in dim_questions:
                # Distribución sesgada hacia valores medios-altos
                opt = random.choices(question.options, weights=[1, 2, 3, 4])[0]
                answers[question.id] = opt.id
                raw += opt.value * question.weight
                max_p += max(o.value for o in question.options) * question.weight
            scores[dim.value] = round(raw / max_p, 4) if max_p > 0 else 0.0

        records.append({
            "scores": scores,
            "answers": answers,
            "cohort_attributes": cohort,
            "quality_score": round(random.uniform(0.75, 1.0), 2),
        })
    return records


def seed_snapshot(force: bool = False) -> str:
    """
    Crea y publica el snapshot inicial.
    Si ya existe un snapshot publicado y force=False, no hace nada.
    Retorna el snapshot_id.
    """
    from benchmark.db.base import get_engine
    from benchmark.db.models import Base
    Base.metadata.create_all(get_engine())

    q = cached_questionnaire("1.0.0")
    hierarchy = cached_cohort_hierarchy("1.0.0")
    privacy = cached_privacy_config("1.0.0")

    with get_session() as session:
        repo = SnapshotRepository()

        if not force:
            existing = repo.get_active_snapshot(session)
            if existing:
                print(f"Snapshot activo ya existe: {existing.snapshot_id}")
                return existing.snapshot_id

        builder = SnapshotBuilder(q, hierarchy, privacy)
        records = _synthetic_records(n=60)
        snapshot = builder.build(
            snapshot_id=str(uuid.uuid4()),
            records=records,
            notes="Snapshot inicial de desarrollo con datos sintéticos",
        )
        repo.save_snapshot(session, snapshot)
        repo.publish_snapshot(session, snapshot.snapshot_id, approved_by="seed_script")
        print(f"Snapshot publicado: {snapshot.snapshot_id}")
        return snapshot.snapshot_id


if __name__ == "__main__":
    seed_snapshot()
