"""
Rutas FastAPI del benchmark.

La API expone casos de uso, no motores individuales.
La DB se inyecta como dependencia — reemplazable en tests.
"""
from __future__ import annotations

import uuid
from typing import Annotated, Generator

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from benchmark.api.schemas import (
    DimensionResultOut,
    FrictionProfileOut,
    OperatorResultOut,
    PdfPayloadOut,
    QuestionnaireOut,
    SubmitResponseIn,
    SubmitResponseOut,
)
from benchmark.application.process_response import ProcessResponseUseCase
from benchmark.config.loader import cached_questionnaire
from benchmark.db.base import get_session
from benchmark.db.repository import ResultRepository, SnapshotRepository
from benchmark.domain.models import (
    BenchmarkSnapshot,
    CohortAttributes,
    OperatorReport,
    RawAnswer,
    RawResponse,
    SnapshotStatus,
)

router = APIRouter(prefix="/api/v1")

_snapshot_repo = SnapshotRepository()
_result_repo = ResultRepository()


# ── Dependencias ──────────────────────────────────────────────────────────────

def _db_session() -> Generator[Session, None, None]:
    with get_session() as session:
        yield session


DbDep = Annotated[Session, Depends(_db_session)]


def _active_snapshot(db: DbDep) -> BenchmarkSnapshot:
    """Carga el snapshot publicado activo. Falla con 503 si no existe."""
    snapshot = _snapshot_repo.get_active_snapshot(db)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No hay snapshot publicado disponible. Ejecutar el job offline primero.",
        )
    return snapshot


SnapshotDep = Annotated[BenchmarkSnapshot, Depends(_active_snapshot)]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/questionnaires/{version}", response_model=QuestionnaireOut)
def get_questionnaire(version: str) -> QuestionnaireOut:
    """Devuelve el cuestionario publicado sin valores de scoring internos."""
    try:
        config = cached_questionnaire(version)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=404, detail=str(e))

    return QuestionnaireOut(
        version=config.version,
        published_at=config.published_at,
        dimensions=[
            {"id": d.id.value, "name": d.name, "description": d.description}
            for d in config.dimensions
        ],
        questions=[
            {
                "id": q.id,
                "dimension": q.dimension.value,
                "text": q.text,
                "options": [{"id": o.id, "label": o.label} for o in q.options],
            }
            for q in config.questions
        ],
    )


@router.post(
    "/responses",
    response_model=SubmitResponseOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_response(
    body: SubmitResponseIn,
    db: DbDep,
    snapshot: SnapshotDep,
) -> SubmitResponseOut:
    """Recibe y procesa una respuesta. Idempotente por idempotency_key."""
    response_id = str(uuid.uuid4())

    raw = RawResponse(
        response_id=response_id,
        questionnaire_version=body.questionnaire_version,
        answers=[
            RawAnswer(question_id=a.question_id, option_id=a.option_id)
            for a in body.answers
        ],
        cohort_attributes=CohortAttributes(
            region=body.cohort_attributes.region,
            dc_type=body.cohort_attributes.dc_type,
            capacity_band=body.cohort_attributes.capacity_band,
            primary_workload=body.cohort_attributes.primary_workload,
        ),
        idempotency_key=body.idempotency_key,
    )

    use_case = ProcessResponseUseCase(
        snapshot=snapshot,
        result_id_factory=lambda: str(uuid.uuid4()),
        methodology_version=body.questionnaire_version,
    )

    result = use_case.execute(
        raw,
        db=db,
        contact_email=body.contact_email,
    )

    return SubmitResponseOut(
        response_id=result.response_id,
        status="processed" if result.success else "rejected",
        rejection_reason=result.rejection_reason,
    )


@router.get("/results/{response_id}", response_model=OperatorResultOut)
def get_result(response_id: str, db: DbDep) -> OperatorResultOut:
    """Devuelve el resultado generado para un response_id."""
    record = _result_repo.get_result_by_response_id(db, response_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Resultado no encontrado")

    report = OperatorReport.model_validate(record.report_json)
    return _report_to_out(report)


@router.get("/results/{response_id}/pdf-payload", response_model=PdfPayloadOut)
def get_pdf_payload(response_id: str, db: DbDep) -> PdfPayloadOut:
    """Payload estable para PDF. No recalcula — usa el resultado persistido."""
    record = _result_repo.get_result_by_response_id(db, response_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Resultado no encontrado")

    report = OperatorReport.model_validate(record.report_json)
    return _report_to_pdf_payload(report)


# ── Helpers de mapeo ──────────────────────────────────────────────────────────

def _report_to_out(report: OperatorReport) -> OperatorResultOut:
    dim_messages = {m.dimension: m for m in report.dimension_messages}
    dims_out = []
    for dr in report.dimension_results:
        msg = dim_messages.get(dr.dimension)
        dims_out.append(DimensionResultOut(
            dimension=dr.dimension.value,
            dimension_label=msg.dimension_label if msg else dr.dimension.value,
            normalized_score=dr.normalized_score,
            percentile=dr.percentile,
            percentile_band=dr.percentile_band,
            confidence_level=dr.confidence_level.value,
            confidence_notes=dr.confidence_notes,
            score_band=msg.score_band if msg else "desconocido",
            specific_message=msg.specific_message if msg else "",
            top_quartile_gap_summary=msg.top_quartile_gap_summary if msg else None,
        ))

    fp = report.friction_profile
    return OperatorResultOut(
        result_id=report.result_id,
        response_id=report.response_id,
        snapshot_id=report.snapshot_id,
        generated_at=report.generated_at,
        questionnaire_version=report.questionnaire_version,
        scoring_version=report.scoring_version,
        cohort_level=report.cohort_assignment.level,
        cohort_level_label=report.cohort_assignment.level_label,
        cohort_fallback_used=len(report.cohort_assignment.fallback_path) > 0,
        executive_summary=report.executive_summary,
        dimensions=dims_out,
        friction_profile=FrictionProfileOut(
            primary_dimension=fp.primary_dimension.value,
            primary_dimension_label=fp.primary_dimension_label,
            severity=fp.severity,
            blocker_types=fp.blocker_types,
            specific_description=fp.specific_description,
            confidence=fp.confidence.value,
        ),
        limitations=report.limitations,
        interpretation_used_llm=report.interpretation_used_llm,
    )


def _report_to_pdf_payload(report: OperatorReport) -> PdfPayloadOut:
    dim_messages = {m.dimension: m for m in report.dimension_messages}
    return PdfPayloadOut(
        result_id=report.result_id,
        response_id=report.response_id,
        snapshot_id=report.snapshot_id,
        generated_at=report.generated_at,
        header={
            "title": "Benchmark de madurez operativa — Data Center",
            "cohort": report.cohort_assignment.level_label,
            "questionnaire_version": report.questionnaire_version,
        },
        executive_summary=report.executive_summary,
        dimension_blocks=[
            {
                "dimension": dr.dimension.value,
                "label": dim_messages[dr.dimension].dimension_label
                if dr.dimension in dim_messages else dr.dimension.value,
                "score": dr.normalized_score,
                "percentile": dr.percentile,
                "band": dr.percentile_band,
                "confidence": dr.confidence_level.value,
                "message": dim_messages[dr.dimension].specific_message
                if dr.dimension in dim_messages else "",
                "tq_gap": dim_messages[dr.dimension].top_quartile_gap_summary
                if dr.dimension in dim_messages else None,
            }
            for dr in report.dimension_results
        ],
        friction_profile={
            "primary_dimension": report.friction_profile.primary_dimension.value,
            "label": report.friction_profile.primary_dimension_label,
            "severity": report.friction_profile.severity,
            "blockers": report.friction_profile.blocker_types,
            "description": report.friction_profile.specific_description,
        },
        methodology_notes=(
            f"Cuestionario v{report.questionnaire_version} · "
            f"Scoring v{report.scoring_version} · "
            f"Snapshot {report.snapshot_id}"
        ),
        version_info={
            "questionnaire": report.questionnaire_version,
            "scoring": report.scoring_version,
            "cohort": report.cohort_version,
            "snapshot": report.snapshot_id,
        },
    )
