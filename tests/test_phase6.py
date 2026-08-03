"""
Tests de Fase 6 — panel interno, drift monitor, LLM con aprobación, validación metodológica.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from benchmark.db.base import Base
from benchmark.db.models import (
    AuditEventRecord,
    BenchmarkSnapshotRecord,
    DimensionScoreRecord,
    ResponseSessionRecord,
)
from benchmark.domain.models import DimensionId, SnapshotStatus
from benchmark.monitoring.dashboard import DashboardService
from benchmark.monitoring.drift_monitor import DriftMonitor
from benchmark.engines.llm_interpretation import (
    LLMInterpretationEngine,
    ProposalStatus,
    ProposalType,
    approve_proposal,
    get_proposal,
    list_pending_proposals,
    reject_proposal,
    save_proposal,
    _proposals_store,
)
from benchmark.jobs.methodology_update import MethodologyUpdateValidator


# ── Fixture DB en memoria ─────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_proposals():
    """Limpia el almacén de propuestas entre tests."""
    _proposals_store.clear()
    yield
    _proposals_store.clear()


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


def _add_snapshot(db, snap_id, status, p50=0.5, published_at=None):
    from benchmark.domain.models import DimensionId
    dists = {
        f"{dim.value}::global": {
            "dimension": dim.value, "cohort_id": "global",
            "percentiles": {"p25": 0.25, "p50": p50, "p75": 0.75, "p90": 0.88},
            "mean": p50, "std": 0.10, "n_effective": 30,
            "top_quartile_threshold": 0.75,
        }
        for dim in DimensionId
    }
    record = BenchmarkSnapshotRecord(
        id=snap_id, status=status,
        questionnaire_version="1.0.0", scoring_version="1.0.0",
        cohort_version="1.0.0", rebalancing_version="1.0.0",
        published_at=published_at or datetime.utcnow(),
        distributions_json=dists,
        top_quartile_practices_json=[],
        rebalancing_weights_json={},
        privacy_thresholds_json={},
    )
    db.add(record)
    db.commit()
    return record


def _add_session_with_scores(db, score_val=0.6):
    sid = str(uuid.uuid4())
    sess = ResponseSessionRecord(
        id=sid, questionnaire_version="1.0.0",
        idempotency_key=str(uuid.uuid4()),
        received_at=datetime.utcnow(),
        region_band="latam", dc_type_band="colo",
        capacity_band="medium", workload_band="general",
        validation_status="valid", quality_score=0.9,
        included_in_dataset=False,
    )
    db.add(sess)
    for dim in DimensionId:
        db.add(DimensionScoreRecord(
            session_id=sid, dimension=dim.value,
            raw_score=score_val * 3, normalized_score=score_val,
            max_possible=3.0, scoring_version="1.0.0",
            blocker_types=[], evidence=[],
        ))
    db.commit()
    return sid


# ── T-06-1: Dashboard ─────────────────────────────────────────────────────────

def test_dashboard_growth_metrics(db):
    _add_snapshot(db, "snap-1", SnapshotStatus.PUBLISHED.value)
    _add_session_with_scores(db)
    _add_session_with_scores(db)
    # Sesión rechazada
    rejected = ResponseSessionRecord(
        id=str(uuid.uuid4()), questionnaire_version="1.0.0",
        idempotency_key=str(uuid.uuid4()), received_at=datetime.utcnow(),
        validation_status="rejected", quality_score=0.0,
        included_in_dataset=False,
    )
    db.add(rejected)
    db.commit()

    report = DashboardService().get_report(db)

    assert report.growth.total_valid == 2
    assert report.growth.total_rejected == 1
    assert report.growth.acceptance_rate == pytest.approx(2/3, abs=0.01)
    assert report.growth.pending_inclusion == 2


def test_dashboard_dimension_quality(db):
    _add_snapshot(db, "snap-1", SnapshotStatus.PUBLISHED.value)
    _add_session_with_scores(db, score_val=0.8)
    _add_session_with_scores(db, score_val=0.4)

    report = DashboardService().get_report(db)

    assert len(report.dimension_quality) == len(DimensionId)
    for dq in report.dimension_quality:
        assert dq.n_responses == 2
        assert 0.0 <= dq.mean_score <= 1.0


def test_dashboard_no_drift_single_snapshot(db):
    _add_snapshot(db, "snap-1", SnapshotStatus.PUBLISHED.value)
    report = DashboardService().get_report(db)
    assert report.snapshot_drift.alert is False
    assert report.snapshot_drift.previous_snapshot_id is None


def test_dashboard_drift_detected(db):
    _add_snapshot(db, "snap-old", SnapshotStatus.PUBLISHED.value,
                  p50=0.8, published_at=datetime.utcnow() - timedelta(days=30))
    _add_snapshot(db, "snap-new", SnapshotStatus.PUBLISHED.value, p50=0.3)

    report = DashboardService().get_report(db)
    assert report.snapshot_drift.alert is True
    assert report.snapshot_drift.max_drift > 0.15


def test_dashboard_audit_summary(db):
    _add_snapshot(db, "snap-1", SnapshotStatus.PUBLISHED.value)
    db.add(AuditEventRecord(event_type="response.received", metadata_json={}))
    db.add(AuditEventRecord(event_type="response.received", metadata_json={}))
    db.add(AuditEventRecord(event_type="result.generated", metadata_json={}))
    db.commit()

    report = DashboardService().get_report(db)
    assert report.audit_summary.get("response.received", 0) == 2
    assert report.audit_summary.get("result.generated", 0) == 1


# ── T-06-2: Drift monitor ─────────────────────────────────────────────────────

def test_drift_monitor_no_previous(db):
    _add_snapshot(db, "snap-1", SnapshotStatus.PUBLISHED.value)
    result = DriftMonitor().check(db)
    assert result.previous_snapshot_id is None
    assert result.alerts == []


def test_drift_monitor_low_drift_no_alert(db):
    _add_snapshot(db, "snap-old", SnapshotStatus.SUPERSEDED.value,
                  p50=0.50, published_at=datetime.utcnow() - timedelta(days=30))
    _add_snapshot(db, "snap-new", SnapshotStatus.PUBLISHED.value, p50=0.53)

    result = DriftMonitor().check(db)
    critical = [a for a in result.alerts if a.severity == "critical"]
    assert len(critical) == 0


def test_drift_monitor_high_drift_critical(db):
    _add_snapshot(db, "snap-old", SnapshotStatus.SUPERSEDED.value,
                  p50=0.9, published_at=datetime.utcnow() - timedelta(days=30))
    _add_snapshot(db, "snap-new", SnapshotStatus.PUBLISHED.value, p50=0.2)

    result = DriftMonitor().check(db)
    assert result.has_critical
    assert any(a.metric == "p50_drift" for a in result.alerts)


def test_drift_monitor_n_drop_warning(db):
    # snapshot anterior con n=100, actual con n=30 (70% drop)
    from benchmark.domain.models import DimensionId
    old_dists = {
        f"{dim.value}::global": {
            "dimension": dim.value, "cohort_id": "global",
            "percentiles": {"p25": 0.25, "p50": 0.5, "p75": 0.75, "p90": 0.88},
            "mean": 0.5, "std": 0.1, "n_effective": 100,
            "top_quartile_threshold": 0.75,
        }
        for dim in DimensionId
    }
    new_dists = {
        f"{dim.value}::global": {
            "dimension": dim.value, "cohort_id": "global",
            "percentiles": {"p25": 0.24, "p50": 0.51, "p75": 0.74, "p90": 0.87},
            "mean": 0.5, "std": 0.1, "n_effective": 20,  # caída del 80%
            "top_quartile_threshold": 0.74,
        }
        for dim in DimensionId
    }
    old_rec = BenchmarkSnapshotRecord(
        id="snap-old2", status=SnapshotStatus.SUPERSEDED.value,
        questionnaire_version="1.0.0", scoring_version="1.0.0",
        cohort_version="1.0.0", rebalancing_version="1.0.0",
        published_at=datetime.utcnow() - timedelta(days=30),
        distributions_json=old_dists,
        top_quartile_practices_json=[], rebalancing_weights_json={}, privacy_thresholds_json={},
    )
    new_rec = BenchmarkSnapshotRecord(
        id="snap-new2", status=SnapshotStatus.PUBLISHED.value,
        questionnaire_version="1.0.0", scoring_version="1.0.0",
        cohort_version="1.0.0", rebalancing_version="1.0.0",
        published_at=datetime.utcnow(),
        distributions_json=new_dists,
        top_quartile_practices_json=[], rebalancing_weights_json={}, privacy_thresholds_json={},
    )
    db.add_all([old_rec, new_rec])
    db.commit()

    result = DriftMonitor().check(db)
    n_drop_alerts = [a for a in result.alerts if a.metric == "n_drop"]
    assert len(n_drop_alerts) > 0


# ── T-06-3: LLM con aprobación humana ────────────────────────────────────────

def test_llm_fallback_when_no_client():
    """Sin cliente LLM el engine usa fallback determinista."""
    engine = LLMInterpretationEngine(llm_client=None)
    proposal = engine.propose_narrative(
        proposal_id=str(uuid.uuid4()),
        friction_dimension="visibility",
        severity="critical",
        blockers=["integration", "budget"],
        base_description="Visibilidad cross-layer baja.",
        percentile=15.0,
        cohort_label="Colo LATAM",
    )
    assert not proposal.used_llm
    assert proposal.generated_text  # fallback no está vacío
    assert proposal.status == ProposalStatus.PENDING


def test_proposal_approval_flow():
    engine = LLMInterpretationEngine()
    pid = str(uuid.uuid4())
    proposal = engine.propose_narrative(
        proposal_id=pid,
        friction_dimension="coordination_latency",
        severity="significant",
        blockers=["process"],
        base_description="Latencia de coordinación manual.",
        percentile=30.0,
        cohort_label="Enterprise",
    )
    save_proposal(proposal)

    pending = list_pending_proposals()
    assert any(p.proposal_id == pid for p in pending)

    approved = approve_proposal(pid, reviewed_by="metodologa@empresa.com", notes="OK")
    assert approved is not None
    assert approved.status == ProposalStatus.APPROVED
    assert approved.reviewed_by == "metodologa@empresa.com"

    # Ya no está en pending
    pending_after = list_pending_proposals()
    assert not any(p.proposal_id == pid for p in pending_after)


def test_proposal_rejection_flow():
    engine = LLMInterpretationEngine()
    pid = str(uuid.uuid4())
    proposal = engine.propose_methodology_action(
        proposal_id=pid,
        drift_dimension="self_quantification",
        drift_value=0.18,
        n_effective=12,
        acceptance_trend="declining",
    )
    save_proposal(proposal)

    rejected = reject_proposal(pid, reviewed_by="revisor@empresa.com",
                               notes="Necesita más contexto")
    assert rejected.status == ProposalStatus.REJECTED
    assert rejected.review_notes == "Necesita más contexto"


def test_proposal_text_not_empty_fallback():
    """El fallback siempre produce texto no vacío."""
    engine = LLMInterpretationEngine(llm_client=None)
    for dim in ["visibility", "friction_attribution", "coordination_latency"]:
        p = engine.propose_narrative(
            proposal_id=str(uuid.uuid4()),
            friction_dimension=dim,
            severity="moderate",
            blockers=[],
            base_description=f"Descripción base de {dim}.",
            percentile=45.0,
            cohort_label="Global",
        )
        assert len(p.generated_text) > 10


def test_methodology_proposal_uses_facts():
    """La propuesta de metodología incluye los hechos en source_facts."""
    engine = LLMInterpretationEngine()
    p = engine.propose_methodology_action(
        proposal_id=str(uuid.uuid4()),
        drift_dimension="blockers",
        drift_value=0.22,
        n_effective=8,
        acceptance_trend="stable",
    )
    assert p.source_facts["drift_dimension"] == "blockers"
    assert p.source_facts["n_effective"] == "8"
    assert p.proposal_type == ProposalType.METHODOLOGY_SUGGESTION


# ── T-06-4: Validación metodológica ──────────────────────────────────────────

def test_methodology_validation_passes_for_v1():
    """La versión 1.0.0 que ya existe debe pasar la validación."""
    validator = MethodologyUpdateValidator()
    result = validator.validate("1.0.0")
    assert result.passed, f"Errores: {result.errors}"
    assert result.checklist["questionnaire_loadable"]
    assert result.checklist["all_dimensions_have_questions"]
    assert result.checklist["positive_weights"]
    assert result.checklist["numeric_option_values"]


def test_methodology_validation_fails_unknown_version():
    """Una versión que no existe debe fallar con error claro."""
    validator = MethodologyUpdateValidator()
    result = validator.validate("99.99.99")
    assert not result.passed
    assert any("questionnaire" in e.lower() or "no encontrado" in e.lower()
               for e in result.errors)


def test_methodology_checklist_all_keys_present():
    """El checklist siempre incluye todas las claves esperadas."""
    validator = MethodologyUpdateValidator()
    result = validator.validate("1.0.0")
    expected_keys = {
        "questionnaire_loadable",
        "cohort_hierarchy_loadable",
        "privacy_config_loadable",
        "all_dimensions_have_questions",
        "all_questions_have_options",
        "positive_weights",
        "numeric_option_values",
        "hierarchy_has_global_level",
        "privacy_thresholds_adequate",
    }
    assert expected_keys.issubset(set(result.checklist.keys()))
