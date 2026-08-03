"""
Tests del job offline BuildSnapshotJob. (Fase 5)

Verifica: construcción de candidato, backtest, pesos de rebalanceo,
rechazo por drift, y que respuestas marcadas como incluidas no se reprocesen.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from benchmark.db.base import Base
from benchmark.db.models import (
    AnswerRecord,
    BenchmarkSnapshotRecord,
    DimensionScoreRecord,
    ResponseSessionRecord,
)
from benchmark.db.repository import SnapshotRepository
from benchmark.domain.models import DimensionId, SnapshotStatus
from benchmark.jobs.build_snapshot import BuildSnapshotJob
from benchmark.config.loader import cached_questionnaire


@pytest.fixture(scope="function")
def db() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def set_pragma(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    SL = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SL()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def _seed_valid_sessions(db: Session, n: int = 15) -> list[str]:
    """
    Inserta n sesiones válidas con scores y respuestas en DB.
    Distribuidas en 3 cohorts para que el snapshot tenga variedad.
    """
    q = cached_questionnaire("1.0.0")
    cohorts = [
        ("latam", "colo", "medium", "general"),
        ("europe", "enterprise", "large", "hpc"),
        ("northam", "hyperscale", "xlarge", "mixed"),
    ]
    ids = []
    for i in range(n):
        region, dc_type, cap, wl = cohorts[i % 3]
        sid = str(uuid.uuid4())
        sess = ResponseSessionRecord(
            id=sid,
            questionnaire_version="1.0.0",
            idempotency_key=str(uuid.uuid4()),
            received_at=datetime.utcnow(),
            region_band=region,
            dc_type_band=dc_type,
            capacity_band=cap,
            workload_band=wl,
            validation_status="valid",
            quality_score=0.9,
            included_in_dataset=False,
        )
        db.add(sess)

        # Respuestas con opciones variadas
        opt_idx = i % 4  # 0-3
        for question in q.questions:
            opt = question.options[opt_idx]
            db.add(AnswerRecord(session_id=sid, question_id=question.id, option_id=opt.id))

        # Scores pre-calculados (simulando que ya pasaron por ScoringEngine)
        for dim in DimensionId:
            db.add(DimensionScoreRecord(
                session_id=sid,
                dimension=dim.value,
                raw_score=float(opt_idx) * 3.0,
                normalized_score=opt_idx / 3.0,
                max_possible=9.0,
                scoring_version="1.0.0",
                blocker_types=[],
                evidence=[],
            ))

        ids.append(sid)

    db.commit()
    return ids


def test_job_creates_draft_snapshot(db):
    _seed_valid_sessions(db, n=15)
    job = BuildSnapshotJob()
    result = job.run(db)
    db.commit()

    assert result.status == "created_draft"
    assert result.records_included == 15
    assert result.snapshot_id != ""

    # El snapshot existe en DB como draft
    snap_repo = SnapshotRepository()
    record = db.get(BenchmarkSnapshotRecord, result.snapshot_id)
    assert record is not None
    assert record.status == SnapshotStatus.DRAFT.value


def test_job_skips_when_no_pending(db):
    result = BuildSnapshotJob().run(db)
    assert result.status == "skipped_no_data"
    assert result.records_included == 0


def test_job_marks_sessions_included(db):
    _seed_valid_sessions(db, n=10)
    job = BuildSnapshotJob()
    job.run(db)
    db.commit()

    # Todas las sesiones deben estar marcadas como incluidas
    sessions = db.query(ResponseSessionRecord).all()
    assert all(s.included_in_dataset for s in sessions)


def test_job_does_not_reprocess_included(db):
    _seed_valid_sessions(db, n=10)
    job = BuildSnapshotJob()

    result1 = job.run(db)
    db.commit()
    assert result1.records_included == 10

    # Segunda ejecución: no hay nuevas sesiones pendientes
    result2 = job.run(db)
    assert result2.status == "skipped_no_data"
    assert result2.records_included == 0


def test_job_passes_backtest_first_snapshot(db):
    """El primer snapshot siempre pasa el backtest (no hay referencia previa)."""
    _seed_valid_sessions(db, n=12)
    job = BuildSnapshotJob()
    result = job.run(db)
    db.commit()

    assert result.backtest is not None
    assert result.backtest.passed
    assert result.backtest.rejection_reasons == []


def test_rebalancing_weights_stored_in_snapshot(db):
    """Los pesos de rebalanceo se almacenan en el snapshot candidato."""
    _seed_valid_sessions(db, n=15)
    job = BuildSnapshotJob()
    result = job.run(db)
    db.commit()

    record = db.get(BenchmarkSnapshotRecord, result.snapshot_id)
    assert record.rebalancing_weights_json  # no vacío
    # Cada peso tiene primary + public que suman 1
    for key, w in record.rebalancing_weights_json.items():
        assert abs(w["primary_weight"] + w["public_weight"] - 1.0) < 1e-5


def test_snapshot_publish_after_job(db):
    """Después del job, el snapshot se puede publicar manualmente."""
    _seed_valid_sessions(db, n=15)
    job = BuildSnapshotJob()
    result = job.run(db)
    db.commit()

    snap_repo = SnapshotRepository()
    snap_repo.publish_snapshot(db, result.snapshot_id, approved_by="test_approver")
    db.commit()

    record = db.get(BenchmarkSnapshotRecord, result.snapshot_id)
    assert record.status == SnapshotStatus.PUBLISHED.value
    assert record.approved_by == "test_approver"


def test_backtest_detects_high_drift(db):
    """
    Si el snapshot vigente tiene distribuciones muy distintas al candidato,
    el backtest debe detectar el drift.
    """
    from benchmark.domain.models import DimensionDistribution, BenchmarkSnapshot
    from benchmark.db.repository import SnapshotRepository

    # Publicar un snapshot con p50 = 0.9 en todas las dimensiones
    snap_repo = SnapshotRepository()
    from benchmark.db.models import BenchmarkSnapshotRecord

    # Construir distribuciones con p50 alto
    high_dists = {
        f"{dim.value}::global": {
            "dimension": dim.value,
            "cohort_id": "global",
            "percentiles": {"p25": 0.70, "p50": 0.90, "p75": 0.95, "p90": 0.99},
            "mean": 0.90, "std": 0.05,
            "n_effective": 100,
            "top_quartile_threshold": 0.95,
        }
        for dim in DimensionId
    }
    existing = BenchmarkSnapshotRecord(
        id="snap-high",
        status=SnapshotStatus.PUBLISHED.value,
        questionnaire_version="1.0.0",
        scoring_version="1.0.0",
        cohort_version="1.0.0",
        rebalancing_version="1.0.0",
        published_at=datetime.utcnow(),
        distributions_json=high_dists,
        top_quartile_practices_json=[],
        rebalancing_weights_json={},
        privacy_thresholds_json={},
    )
    db.add(existing)
    db.commit()

    # Seed con scores bajos (cerca de 0) → gran drift contra p50=0.9
    _seed_valid_sessions(db, n=15)
    # Ajustar scores a valores bajos para forzar drift
    db.query(DimensionScoreRecord).update({"normalized_score": 0.05})
    db.commit()

    job = BuildSnapshotJob()
    result = job.run(db)
    db.commit()

    # El backtest debe detectar drift alto y fallar
    assert result.backtest is not None
    assert not result.backtest.passed
    assert len(result.backtest.rejection_reasons) > 0
