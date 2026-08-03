"""
Modelos de dominio del benchmark.

Estas clases son pure Python / Pydantic — sin dependencia de DB, API ni LLM.
Son los contratos entre motores.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enumeraciones ─────────────────────────────────────────────────────────────

class DimensionId(str, Enum):
    VISIBILITY = "visibility"
    FRICTION_ATTRIBUTION = "friction_attribution"
    COORDINATION_LATENCY = "coordination_latency"
    SELF_QUANTIFICATION = "self_quantification"
    BLOCKERS = "blockers"


class ValidationStatus(str, Enum):
    VALID = "valid"
    REJECTED = "rejected"


class SnapshotStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"


class ConfidenceLevel(str, Enum):
    HIGH = "high"      # n_effective >= umbral * 2
    MEDIUM = "medium"  # n_effective >= umbral
    LOW = "low"        # fallback activado o n_effective < umbral
    INSUFFICIENT = "insufficient"  # no hay datos usables


# ── Config metodológica (cargada desde YAML) ──────────────────────────────────

class AnswerOptionConfig(BaseModel):
    id: str
    value: float
    label: str
    blocker_type: str | None = None


class QuestionConfig(BaseModel):
    id: str
    dimension: DimensionId
    text: str
    weight: float = 1.0
    is_blocker: bool = False
    options: list[AnswerOptionConfig]


class DimensionConfig(BaseModel):
    id: DimensionId
    name: str
    description: str


class CohortAttributeBand(BaseModel):
    id: str
    label: str


class CohortAttributeConfig(BaseModel):
    id: str
    label: str
    bands: list[CohortAttributeBand]


class QuestionnaireConfig(BaseModel):
    version: str
    published_at: str
    status: str
    dimensions: list[DimensionConfig]
    questions: list[QuestionConfig]
    cohort_attributes: list[CohortAttributeConfig]

    def get_question(self, question_id: str) -> QuestionConfig | None:
        return next((q for q in self.questions if q.id == question_id), None)

    def get_option(self, question_id: str, option_id: str) -> AnswerOptionConfig | None:
        q = self.get_question(question_id)
        if q is None:
            return None
        return next((o for o in q.options if o.id == option_id), None)

    def questions_for_dimension(self, dim: DimensionId) -> list[QuestionConfig]:
        return [q for q in self.questions if q.dimension == dim]


class CohortLevel(BaseModel):
    level: int
    label: str
    attributes: list[str]


class CohortHierarchyConfig(BaseModel):
    version: str
    hierarchy: list[CohortLevel]


class PrivacyConfig(BaseModel):
    version: str
    min_cohort_size: int
    min_top_quartile_support: int
    min_effective_n_for_percentile: int


# ── Entradas del sistema ──────────────────────────────────────────────────────

class RawAnswer(BaseModel):
    question_id: str
    option_id: str


class CohortAttributes(BaseModel):
    """Atributos de cohorte enviados por el operador (ya en bandas)."""
    region: str | None = None
    dc_type: str | None = None
    capacity_band: str | None = None
    primary_workload: str | None = None

    def as_dict(self) -> dict[str, str]:
        return {k: v for k, v in self.model_dump().items() if v is not None}


class RawResponse(BaseModel):
    """Respuesta cruda recibida del formulario."""
    response_id: str          # ULID generado en la API, opaco
    questionnaire_version: str
    answers: list[RawAnswer]
    cohort_attributes: CohortAttributes
    idempotency_key: str
    received_at: datetime = Field(default_factory=datetime.utcnow)


# ── Resultados de ValidationEngine ───────────────────────────────────────────

class ValidationError(BaseModel):
    code: str
    question_id: str | None = None
    message: str


class ValidationWarning(BaseModel):
    code: str
    question_id: str | None = None
    message: str


class ValidationResult(BaseModel):
    response_id: str
    questionnaire_version: str
    status: ValidationStatus
    errors: list[ValidationError] = Field(default_factory=list)
    warnings: list[ValidationWarning] = Field(default_factory=list)
    quality_score: float = Field(ge=0.0, le=1.0, default=0.0)
    validated_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def is_valid(self) -> bool:
        return self.status == ValidationStatus.VALID


# ── Resultados de ScoringEngine ───────────────────────────────────────────────

class AnswerEvidence(BaseModel):
    question_id: str
    option_id: str
    raw_value: float
    weight: float
    weighted_contribution: float


class DimensionScore(BaseModel):
    dimension: DimensionId
    raw_score: float           # suma ponderada de valores
    normalized_score: float    # [0.0, 1.0]
    max_possible: float        # para auditoría
    evidence: list[AnswerEvidence]
    blocker_types: list[str] = Field(default_factory=list)  # solo para dimensión blockers
    scoring_version: str


class ScoringResult(BaseModel):
    response_id: str
    questionnaire_version: str
    scoring_version: str
    dimension_scores: list[DimensionScore]

    def get_dimension(self, dim: DimensionId) -> DimensionScore | None:
        return next((d for d in self.dimension_scores if d.dimension == dim), None)


# ── Resultados de CohortEngine ────────────────────────────────────────────────

class CohortAssignment(BaseModel):
    response_id: str
    cohort_id: str             # ej: "region=latam|dc_type=colo|capacity_band=medium"
    level: int                 # nivel de la jerarquía aplicado (1=más específico, 5=global)
    level_label: str
    attributes_used: dict[str, str]
    fallback_path: list[int]   # niveles intentados antes del seleccionado
    effective_n: int           # tamaño de la cohorte en el snapshot
    cohort_version: str
    privacy_suppressed: bool = False  # True si ni el global supera el umbral


# ── Snapshot de benchmark ─────────────────────────────────────────────────────

class DimensionDistribution(BaseModel):
    dimension: DimensionId
    cohort_id: str
    percentiles: dict[str, float]   # "p25", "p50", "p75", "p90"
    mean: float
    std: float
    n_effective: int
    top_quartile_threshold: float   # valor mínimo de score para estar en top 25%


class TopQuartilePractice(BaseModel):
    dimension: DimensionId
    cohort_id: str
    question_id: str
    option_id: str
    frequency_in_top: float         # % operadores top con esta opción
    frequency_in_rest: float        # % en el resto
    difference: float               # frequency_in_top - frequency_in_rest
    statistical_support: int        # n que soporta la afirmación


class BenchmarkSnapshot(BaseModel):
    snapshot_id: str
    status: SnapshotStatus
    published_at: datetime | None
    questionnaire_version: str
    scoring_version: str
    cohort_version: str
    rebalancing_version: str
    primary_data_cutoff: datetime | None
    distributions: list[DimensionDistribution]
    top_quartile_practices: list[TopQuartilePractice]
    rebalancing_weights: dict[str, Any] = Field(default_factory=dict)
    privacy_thresholds: dict[str, Any] = Field(default_factory=dict)
    methodology_notes: str = ""

    def get_distribution(
        self, dim: DimensionId, cohort_id: str
    ) -> DimensionDistribution | None:
        return next(
            (d for d in self.distributions if d.dimension == dim and d.cohort_id == cohort_id),
            None,
        )

    def get_top_quartile_practices(
        self, dim: DimensionId, cohort_id: str
    ) -> list[TopQuartilePractice]:
        return [
            p for p in self.top_quartile_practices
            if p.dimension == dim and p.cohort_id == cohort_id
        ]


# ── Resultados de BenchmarkEngine ────────────────────────────────────────────

class DimensionBenchmarkResult(BaseModel):
    dimension: DimensionId
    normalized_score: float
    percentile: float | None          # None si hay supresión
    percentile_band: str | None       # "p25-p50", etc.
    reference_mean: float | None
    reference_p50: float | None
    confidence_level: ConfidenceLevel
    confidence_notes: list[str] = Field(default_factory=list)
    cohort_id: str
    cohort_level: int
    effective_n: int
    suppressed: bool = False


class BenchmarkResult(BaseModel):
    response_id: str
    snapshot_id: str
    cohort_assignment: CohortAssignment
    dimension_results: list[DimensionBenchmarkResult]
    calculated_at: datetime = Field(default_factory=datetime.utcnow)

    def get_dimension(self, dim: DimensionId) -> DimensionBenchmarkResult | None:
        return next((d for d in self.dimension_results if d.dimension == dim), None)


# ── Resultados de TopQuartileEngine ──────────────────────────────────────────

class TopQuartileGap(BaseModel):
    dimension: DimensionId
    question_id: str
    question_text: str
    operator_option_id: str
    operator_option_label: str
    top_quartile_most_common_option_id: str
    top_quartile_most_common_option_label: str
    gap_description: str
    statistical_support: int


class TopQuartileAnalysis(BaseModel):
    response_id: str
    snapshot_id: str
    cohort_id: str
    gaps: list[TopQuartileGap]
    suppressed_dimensions: list[DimensionId] = Field(default_factory=list)


# ── Perfil de fricción e interpretación ──────────────────────────────────────

class FrictionProfile(BaseModel):
    primary_dimension: DimensionId
    primary_dimension_label: str
    severity: str                  # "critical", "significant", "moderate"
    blocker_types: list[str]
    specific_description: str      # descripción específica, no genérica
    confidence: ConfidenceLevel


class DimensionMessage(BaseModel):
    dimension: DimensionId
    dimension_label: str
    score_band: str               # "bajo", "medio-bajo", "medio-alto", "alto"
    percentile_text: str | None
    specific_message: str
    top_quartile_gap_summary: str | None


class OperatorReport(BaseModel):
    response_id: str
    result_id: str
    snapshot_id: str
    questionnaire_version: str
    scoring_version: str
    cohort_version: str
    rebalancing_version: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    cohort_assignment: CohortAssignment
    dimension_results: list[DimensionBenchmarkResult]
    friction_profile: FrictionProfile
    dimension_messages: list[DimensionMessage]
    top_quartile_analysis: TopQuartileAnalysis
    executive_summary: str
    limitations: list[str] = Field(default_factory=list)
    interpretation_used_llm: bool = False
