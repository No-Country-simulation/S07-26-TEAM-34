"""
Endpoints del panel interno (admin). No son públicos.

En producción proteger con autenticación (API key, OAuth, etc.).
Aquí se expone sin auth para desarrollo — añadir middleware en producción.
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any, Generator

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from benchmark.db.base import get_session
from benchmark.db.repository import SnapshotRepository
from benchmark.engines.llm_interpretation import (
    LLMInterpretationEngine,
    ProposalType,
    approve_proposal,
    get_proposal,
    list_pending_proposals,
    reject_proposal,
    save_proposal,
)
from benchmark.monitoring.dashboard import DashboardService
from benchmark.monitoring.drift_monitor import DriftMonitor

admin_router = APIRouter(prefix="/admin/v1", tags=["admin"])


def _db_session() -> Generator[Session, None, None]:
    with get_session() as session:
        yield session


DbDep = Annotated[Session, Depends(_db_session)]


# ── T-06-1: Panel de calidad ──────────────────────────────────────────────────

@admin_router.get("/dashboard")
def get_dashboard(db: DbDep) -> dict[str, Any]:
    """Panel interno: métricas de calidad, crecimiento y drift."""
    svc = DashboardService()
    report = svc.get_report(db)
    return {
        "generated_at": report.generated_at.isoformat(),
        "growth": {
            "total_valid": report.growth.total_valid,
            "total_rejected": report.growth.total_rejected,
            "acceptance_rate": report.growth.acceptance_rate,
            "new_last_7d": report.growth.new_last_7d,
            "new_last_30d": report.growth.new_last_30d,
            "included_in_dataset": report.growth.included_in_dataset,
            "pending_inclusion": report.growth.pending_inclusion,
        },
        "dimension_quality": [
            {
                "dimension": dq.dimension,
                "n_responses": dq.n_responses,
                "mean_score": dq.mean_score,
                "std_score": dq.std_score,
                "mean_quality": dq.mean_quality,
            }
            for dq in report.dimension_quality
        ],
        "snapshot_drift": {
            "current_snapshot_id": report.snapshot_drift.current_snapshot_id,
            "previous_snapshot_id": report.snapshot_drift.previous_snapshot_id,
            "drift_by_dimension": report.snapshot_drift.drift_by_dimension,
            "max_drift": report.snapshot_drift.max_drift,
            "alert": report.snapshot_drift.alert,
        },
        "audit_summary_24h": report.audit_summary,
    }


# ── T-06-2: Monitor de drift ──────────────────────────────────────────────────

@admin_router.get("/drift-alerts")
def get_drift_alerts(db: DbDep) -> dict[str, Any]:
    """Alertas de drift entre el snapshot actual y el anterior."""
    monitor = DriftMonitor()
    result = monitor.check(db)
    return {
        "checked_at": result.checked_at.isoformat(),
        "current_snapshot_id": result.current_snapshot_id,
        "previous_snapshot_id": result.previous_snapshot_id,
        "has_critical": result.has_critical,
        "summary": result.summary,
        "alerts": [
            {
                "severity": a.severity,
                "dimension": a.dimension,
                "cohort_id": a.cohort_id,
                "metric": a.metric,
                "current_value": a.current_value,
                "previous_value": a.previous_value,
                "delta": a.delta,
                "message": a.message,
            }
            for a in result.alerts
        ],
    }


# ── T-06-3: Propuestas LLM con aprobación humana ─────────────────────────────

class NarrativeProposalIn(BaseModel):
    friction_dimension: str
    severity: str
    blockers: list[str]
    base_description: str
    percentile: float | None = None
    cohort_label: str


class MethodologyProposalIn(BaseModel):
    drift_dimension: str
    drift_value: float
    n_effective: int
    acceptance_trend: str = "stable"


class ReviewIn(BaseModel):
    reviewed_by: str
    notes: str = ""


@admin_router.post("/proposals/narrative")
def create_narrative_proposal(body: NarrativeProposalIn) -> dict[str, Any]:
    """
    Genera una propuesta de narrativa asistida por LLM.
    La propuesta queda en PENDING hasta aprobación explícita.
    """
    engine = LLMInterpretationEngine(llm_client=None)  # fallback determinista
    proposal = engine.propose_narrative(
        proposal_id=str(uuid.uuid4()),
        friction_dimension=body.friction_dimension,
        severity=body.severity,
        blockers=body.blockers,
        base_description=body.base_description,
        percentile=body.percentile,
        cohort_label=body.cohort_label,
    )
    save_proposal(proposal)
    return _proposal_to_dict(proposal)


@admin_router.post("/proposals/methodology")
def create_methodology_proposal(body: MethodologyProposalIn) -> dict[str, Any]:
    """
    Genera una propuesta de acción metodológica asistida por LLM.
    Requiere aprobación humana antes de aplicar cualquier cambio.
    """
    engine = LLMInterpretationEngine(llm_client=None)
    proposal = engine.propose_methodology_action(
        proposal_id=str(uuid.uuid4()),
        drift_dimension=body.drift_dimension,
        drift_value=body.drift_value,
        n_effective=body.n_effective,
        acceptance_trend=body.acceptance_trend,
    )
    save_proposal(proposal)
    return _proposal_to_dict(proposal)


@admin_router.get("/proposals/pending")
def get_pending_proposals() -> list[dict[str, Any]]:
    """Lista todas las propuestas pendientes de revisión."""
    return [_proposal_to_dict(p) for p in list_pending_proposals()]


@admin_router.get("/proposals/{proposal_id}")
def get_proposal_detail(proposal_id: str) -> dict[str, Any]:
    p = get_proposal(proposal_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Propuesta no encontrada")
    return _proposal_to_dict(p)


@admin_router.post("/proposals/{proposal_id}/approve")
def approve(proposal_id: str, body: ReviewIn) -> dict[str, Any]:
    """Aprueba una propuesta. La aprobación queda registrada con nombre del revisor."""
    p = approve_proposal(proposal_id, body.reviewed_by, body.notes)
    if p is None:
        raise HTTPException(status_code=404, detail="Propuesta no encontrada")
    return _proposal_to_dict(p)


@admin_router.post("/proposals/{proposal_id}/reject")
def reject(proposal_id: str, body: ReviewIn) -> dict[str, Any]:
    """Rechaza una propuesta con motivo."""
    p = reject_proposal(proposal_id, body.reviewed_by, body.notes)
    if p is None:
        raise HTTPException(status_code=404, detail="Propuesta no encontrada")
    return _proposal_to_dict(p)


# ── T-06-4: Validación metodológica ──────────────────────────────────────────

@admin_router.post("/methodology/validate/{version}")
def validate_methodology(version: str) -> dict[str, Any]:
    """
    Valida una nueva versión metodológica contra el checklist completo.
    No modifica nada — solo verifica.
    """
    from benchmark.jobs.methodology_update import MethodologyUpdateValidator
    validator = MethodologyUpdateValidator()
    result = validator.validate(version)
    return {
        "version": result.version,
        "passed": result.passed,
        "errors": result.errors,
        "warnings": result.warnings,
        "checklist": result.checklist,
        "next_steps": (
            [
                "Ejecutar job build_snapshot para generar snapshot candidato",
                "Revisar backtest en /admin/v1/drift-alerts",
                "Documentar ADR con la decisión",
                "Publicar con aprobación explícita vía SnapshotRepository.publish_snapshot()",
            ]
            if result.passed else
            ["Corregir los errores indicados antes de proceder"]
        ),
    }


@admin_router.post("/snapshots/{snapshot_id}/publish")
def publish_snapshot(
    snapshot_id: str,
    body: ReviewIn,
    db: DbDep,
) -> dict[str, Any]:
    """
    Publica un snapshot DRAFT de forma atómica.
    Requiere nombre del aprobador. Marca el anterior como superseded.
    """
    repo = SnapshotRepository()
    try:
        repo.publish_snapshot(db, snapshot_id, approved_by=body.reviewed_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "snapshot_id": snapshot_id,
        "status": "published",
        "approved_by": body.reviewed_by,
    }


# ── helper ────────────────────────────────────────────────────────────────────

def _proposal_to_dict(p) -> dict[str, Any]:
    return {
        "proposal_id": p.proposal_id,
        "proposal_type": p.proposal_type.value,
        "status": p.status.value,
        "prompt_version": p.prompt_version,
        "generated_text": p.generated_text,
        "used_llm": p.used_llm,
        "created_at": p.created_at.isoformat(),
        "reviewed_by": p.reviewed_by,
        "reviewed_at": p.reviewed_at.isoformat() if p.reviewed_at else None,
        "review_notes": p.review_notes,
        "source_facts": p.source_facts,
    }
