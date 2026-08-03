"""
InterpretationEngine — ensambla el perfil de fricción y el reporte final. (RF-07, RF-08)

El LLM puede enriquecer el texto si está disponible.
Fallback determinista obligatorio — el sistema nunca falla por ausencia de LLM. (ADR-008)
"""
from __future__ import annotations

from benchmark.domain.models import (
    BenchmarkResult,
    ConfidenceLevel,
    DimensionId,
    DimensionMessage,
    FrictionProfile,
    OperatorReport,
    QuestionnaireConfig,
    ScoringResult,
    TopQuartileAnalysis,
)

_SCORE_BANDS = [
    (0.0,  0.25, "bajo"),
    (0.25, 0.50, "medio-bajo"),
    (0.50, 0.75, "medio-alto"),
    (0.75, 1.01, "alto"),
]

_SEVERITY_THRESHOLDS = {
    "critical":    0.25,
    "significant": 0.50,
    "moderate":    0.75,
}

_DIM_LABELS = {
    DimensionId.VISIBILITY:             "Visibilidad cross-layer",
    DimensionId.FRICTION_ATTRIBUTION:   "Atribución de fricción",
    DimensionId.COORDINATION_LATENCY:   "Latencia de coordinación",
    DimensionId.SELF_QUANTIFICATION:    "Auto-cuantificación",
    DimensionId.BLOCKERS:               "Bloqueantes",
}


def _score_band(score: float) -> str:
    for lo, hi, label in _SCORE_BANDS:
        if lo <= score < hi:
            return label
    return "alto"


def _severity(score: float) -> str:
    if score < _SEVERITY_THRESHOLDS["critical"]:
        return "critical"
    if score < _SEVERITY_THRESHOLDS["significant"]:
        return "significant"
    return "moderate"


class InterpretationEngine:
    """
    Ensambla el reporte final desde hechos estructurados.
    No inventa datos ni infiere causalidad no demostrada.
    """

    def __init__(self, questionnaire: QuestionnaireConfig) -> None:
        self._q = questionnaire

    def build_report(
        self,
        result_id: str,
        scoring: ScoringResult,
        benchmark: BenchmarkResult,
        top_quartile: TopQuartileAnalysis,
        snapshot_id: str,
        rebalancing_version: str = "1.0.0",
    ) -> OperatorReport:
        friction = self._build_friction_profile(scoring, benchmark)
        dim_messages = self._build_dimension_messages(scoring, benchmark, top_quartile)
        summary = self._build_executive_summary(friction, dim_messages, benchmark)
        limitations = self._build_limitations(benchmark)

        return OperatorReport(
            response_id=scoring.response_id,
            result_id=result_id,
            snapshot_id=snapshot_id,
            questionnaire_version=scoring.questionnaire_version,
            scoring_version=scoring.scoring_version,
            cohort_version=benchmark.cohort_assignment.cohort_version,
            rebalancing_version=rebalancing_version,
            cohort_assignment=benchmark.cohort_assignment,
            dimension_results=benchmark.dimension_results,
            friction_profile=friction,
            dimension_messages=dim_messages,
            top_quartile_analysis=top_quartile,
            executive_summary=summary,
            limitations=limitations,
            interpretation_used_llm=False,
        )

    # ── privados ──────────────────────────────────────────────────────────────

    def _build_friction_profile(
        self, scoring: ScoringResult, benchmark: BenchmarkResult
    ) -> FrictionProfile:
        # Dimensión con peor posición relativa (percentil más bajo no suprimido)
        worst_dim_result = min(
            (r for r in benchmark.dimension_results if not r.suppressed and r.percentile is not None),
            key=lambda r: r.percentile or 0.0,
            default=None,
        )

        # Si todo está suprimido, usar el score más bajo
        if worst_dim_result is None:
            worst_score = min(scoring.dimension_scores, key=lambda d: d.normalized_score)
            primary_dim = worst_score.dimension
            score_val = worst_score.normalized_score
            confidence = ConfidenceLevel.INSUFFICIENT
        else:
            primary_dim = worst_dim_result.dimension
            score_val = worst_dim_result.normalized_score
            confidence = worst_dim_result.confidence_level

        # Bloqueantes activos
        blocker_score = next(
            (s for s in scoring.dimension_scores if s.dimension == DimensionId.BLOCKERS), None
        )
        blocker_types = blocker_score.blocker_types if blocker_score else []

        severity = _severity(score_val)
        description = self._friction_description(primary_dim, score_val, blocker_types, scoring)

        return FrictionProfile(
            primary_dimension=primary_dim,
            primary_dimension_label=_DIM_LABELS[primary_dim],
            severity=severity,
            blocker_types=blocker_types,
            specific_description=description,
            confidence=confidence,
        )

    def _friction_description(
        self,
        dim: DimensionId,
        score: float,
        blocker_types: list[str],
        scoring: ScoringResult,
    ) -> str:
        band = _score_band(score)
        base = f"Posición {band} en {_DIM_LABELS[dim]}"

        # Contexto cruzado entre dimensiones para ser específico
        vis = next((s for s in scoring.dimension_scores if s.dimension == DimensionId.VISIBILITY), None)
        lat = next((s for s in scoring.dimension_scores if s.dimension == DimensionId.COORDINATION_LATENCY), None)

        context = ""
        if dim == DimensionId.COORDINATION_LATENCY and vis and vis.normalized_score > 0.5:
            context = " con visibilidad cross-layer aceptable pero coordinación manual entre capas"
        elif dim == DimensionId.FRICTION_ATTRIBUTION and lat and lat.normalized_score < 0.5:
            context = " con dificultad para localizar pérdidas y latencia de coordinación elevada"
        elif dim == DimensionId.VISIBILITY:
            context = " — observación de energía, cooling y workloads fragmentada o poco frecuente"

        blockers_text = ""
        if blocker_types:
            blockers_text = f". Bloqueantes identificados: {', '.join(blocker_types)}"

        return f"{base}{context}{blockers_text}."

    def _build_dimension_messages(
        self,
        scoring: ScoringResult,
        benchmark: BenchmarkResult,
        top_quartile: TopQuartileAnalysis,
    ) -> list[DimensionMessage]:
        messages: list[DimensionMessage] = []
        tq_gaps_by_dim = {}
        for gap in top_quartile.gaps:
            tq_gaps_by_dim.setdefault(gap.dimension, []).append(gap)

        for dim_score in scoring.dimension_scores:
            dim = dim_score.dimension
            bench = benchmark.get_dimension(dim)
            band = _score_band(dim_score.normalized_score)

            percentile_text = None
            if bench and bench.percentile is not None and not bench.suppressed:
                p = bench.percentile
                percentile_text = f"Percentil {p:.0f} en su grupo de referencia"

            gaps = tq_gaps_by_dim.get(dim, [])
            tq_summary = None
            if gaps:
                first = gaps[0]
                tq_summary = (
                    f"El cuartil superior {first.gap_description.split('.')[0].lower()}"
                )

            message = self._dimension_message(dim, band, gaps)

            messages.append(DimensionMessage(
                dimension=dim,
                dimension_label=_DIM_LABELS[dim],
                score_band=band,
                percentile_text=percentile_text,
                specific_message=message,
                top_quartile_gap_summary=tq_summary,
            ))
        return messages

    @staticmethod
    def _dimension_message(dim: DimensionId, band: str, gaps: list) -> str:
        templates = {
            DimensionId.VISIBILITY: {
                "bajo": "La consolidación de métricas entre capas es mínima o inexistente. Prioridad alta.",
                "medio-bajo": "Hay visibilidad parcial pero la correlación entre capas es manual o incompleta.",
                "medio-alto": "Buena visibilidad en la mayoría de activos. Oportunidad en automatización de correlación.",
                "alto": "Visibilidad cross-layer bien establecida y automatizada.",
            },
            DimensionId.FRICTION_ATTRIBUTION: {
                "bajo": "No existe capacidad para localizar pérdidas de capacidad en interfaces específicas.",
                "medio-bajo": "La atribución de fricción es posible pero requiere esfuerzo manual significativo.",
                "medio-alto": "Proceso documentado de atribución. Oportunidad en cuantificación sistemática.",
                "alto": "Atribución de fricción sistemática con evidencia cuantitativa.",
            },
            DimensionId.COORDINATION_LATENCY: {
                "bajo": "Ajustes entre capas toman horas o no ocurren. Alta probabilidad de stranded capacity.",
                "medio-bajo": "Coordinación entre capas es manual con runbooks. Latencia de 30+ minutos.",
                "medio-alto": "Coordinación semi-automatizada. Oportunidad en reducir latencia residual.",
                "alto": "Coordinación automatizada con latencia menor a 5 minutos.",
            },
            DimensionId.SELF_QUANTIFICATION: {
                "bajo": "Sin estimación formal de stranded capacity. Sin base para decisiones de capacidad.",
                "medio-bajo": "Estimación cualitativa o de baja confianza. Metodología sin validar.",
                "medio-alto": "Estimación cuantitativa con cobertura parcial. Oportunidad en validación.",
                "alto": "Estimación sistemática, validada y usada en planificación de capacidad.",
            },
            DimensionId.BLOCKERS: {
                "bajo": "Bloqueantes múltiples activos sin plan de resolución formal.",
                "medio-bajo": "Bloqueantes identificados pero con gestión informal.",
                "medio-alto": "Gestión activa de bloqueantes con responsables asignados.",
                "alto": "Bloqueantes bajo control con seguimiento regular y planes vigentes.",
            },
        }
        return templates.get(dim, {}).get(band, f"Posición {band} en {_DIM_LABELS.get(dim, dim.value)}.")

    @staticmethod
    def _build_executive_summary(
        friction: FrictionProfile,
        messages: list[DimensionMessage],
        benchmark: BenchmarkResult,
    ) -> str:
        cohort_label = benchmark.cohort_assignment.level_label
        high_dims = [m.dimension_label for m in messages if m.score_band == "alto"]
        low_dims = [m.dimension_label for m in messages if m.score_band in ("bajo", "medio-bajo")]

        parts = [f"Evaluación comparada contra: {cohort_label}."]

        if high_dims:
            parts.append(f"Dimensiones con posición alta: {', '.join(high_dims)}.")
        if low_dims:
            parts.append(f"Dimensiones con mayor oportunidad de mejora: {', '.join(low_dims)}.")

        parts.append(
            f"Fricción principal identificada en '{friction.primary_dimension_label}' "
            f"(severidad: {friction.severity}). {friction.specific_description}"
        )

        if benchmark.cohort_assignment.privacy_suppressed:
            parts.append(
                "Nota: la comparación con pares no está disponible por tamaño insuficiente de muestra."
            )

        return " ".join(parts)

    @staticmethod
    def _build_limitations(benchmark: BenchmarkResult) -> list[str]:
        limitations: list[str] = []
        if benchmark.cohort_assignment.privacy_suppressed:
            limitations.append("Comparación con grupo de referencia no disponible por privacidad.")
        if benchmark.cohort_assignment.level > 2:
            limitations.append(
                f"Comparación basada en grupo amplio (nivel {benchmark.cohort_assignment.level}). "
                "Resultado menos específico que el ideal."
            )
        suppressed = [r for r in benchmark.dimension_results if r.suppressed]
        if suppressed:
            dims = ", ".join(r.dimension.value for r in suppressed)
            limitations.append(f"Percentiles no disponibles para: {dims}.")
        low_conf = [
            r for r in benchmark.dimension_results
            if r.confidence_level in (ConfidenceLevel.LOW, ConfidenceLevel.INSUFFICIENT)
        ]
        if low_conf:
            limitations.append(
                "Confianza baja en algunas dimensiones por tamaño de muestra limitado."
            )
        return limitations
