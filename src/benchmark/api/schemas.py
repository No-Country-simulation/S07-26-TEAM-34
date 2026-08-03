"""Schemas de entrada/salida de la API. Sin lógica de negocio."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Entrada ───────────────────────────────────────────────────────────────────

class AnswerIn(BaseModel):
    question_id: str
    option_id: str


class CohortAttributesIn(BaseModel):
    region: str | None = None
    dc_type: str | None = None
    capacity_band: str | None = None
    primary_workload: str | None = None


class SubmitResponseIn(BaseModel):
    questionnaire_version: str
    answers: list[AnswerIn]
    cohort_attributes: CohortAttributesIn
    idempotency_key: str
    contact_email: str | None = None  # va a almacén separado, nunca a scoring


# ── Salida ────────────────────────────────────────────────────────────────────

class SubmitResponseOut(BaseModel):
    response_id: str
    status: str
    rejection_reason: str | None = None


class DimensionResultOut(BaseModel):
    dimension: str
    dimension_label: str
    normalized_score: float
    percentile: float | None
    percentile_band: str | None
    confidence_level: str
    confidence_notes: list[str]
    score_band: str
    specific_message: str
    top_quartile_gap_summary: str | None


class FrictionProfileOut(BaseModel):
    primary_dimension: str
    primary_dimension_label: str
    severity: str
    blocker_types: list[str]
    specific_description: str
    confidence: str


class OperatorResultOut(BaseModel):
    result_id: str
    response_id: str
    snapshot_id: str
    generated_at: datetime
    questionnaire_version: str
    scoring_version: str
    cohort_level: int
    cohort_level_label: str
    cohort_fallback_used: bool
    executive_summary: str
    dimensions: list[DimensionResultOut]
    friction_profile: FrictionProfileOut
    limitations: list[str]
    interpretation_used_llm: bool


class PdfPayloadOut(BaseModel):
    """Payload estable para generación de PDF. No recalcula nada."""
    result_id: str
    response_id: str
    snapshot_id: str
    generated_at: datetime
    header: dict[str, Any]
    executive_summary: str
    dimension_blocks: list[dict[str, Any]]
    friction_profile: dict[str, Any]
    methodology_notes: str
    version_info: dict[str, str]


class QuestionnaireOut(BaseModel):
    version: str
    published_at: str
    dimensions: list[dict[str, str]]
    questions: list[dict[str, Any]]   # sin scoreValues internos
