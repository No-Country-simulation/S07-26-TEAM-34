"""
BenchmarkEngine — calcula percentiles y confianza contra snapshot publicado. (RF-05)

Sin dependencia de DB ni LLM. Determinista.
"""
from __future__ import annotations

import math

from benchmark.domain.models import (
    BenchmarkResult,
    CohortAssignment,
    ConfidenceLevel,
    DimensionBenchmarkResult,
    DimensionId,
    PrivacyConfig,
    ScoringResult,
    BenchmarkSnapshot,
)

_PERCENTILE_BANDS = [
    (0.0,  25.0,  "p0-p25",   "Cuartil inferior"),
    (25.0, 50.0,  "p25-p50",  "Por debajo de la mediana"),
    (50.0, 75.0,  "p50-p75",  "Por encima de la mediana"),
    (75.0, 100.0, "p75-p100", "Cuartil superior"),
]


def _percentile_band(p: float) -> str:
    for lo, hi, band, _ in _PERCENTILE_BANDS:
        if lo <= p <= hi:
            return band
    return "p75-p100"


def _confidence(n_effective: int, min_n: int, used_fallback: bool) -> tuple[ConfidenceLevel, list[str]]:
    notes: list[str] = []
    if used_fallback:
        notes.append("Comparación basada en grupo más amplio por tamaño insuficiente de cohorte específica")
    if n_effective >= min_n * 2:
        level = ConfidenceLevel.HIGH
    elif n_effective >= min_n:
        level = ConfidenceLevel.MEDIUM
        notes.append("Muestra en el límite mínimo; considerar banda percentil en lugar de percentil exacto")
    else:
        level = ConfidenceLevel.LOW
        notes.append("Muestra insuficiente; resultado orientativo")
    return level, notes


class BenchmarkEngine:
    def __init__(self, privacy: PrivacyConfig) -> None:
        self._privacy = privacy

    def calculate(
        self,
        scoring: ScoringResult,
        cohort: CohortAssignment,
        snapshot: BenchmarkSnapshot,
    ) -> BenchmarkResult:
        results: list[DimensionBenchmarkResult] = []
        used_fallback = len(cohort.fallback_path) > 0

        for dim_score in scoring.dimension_scores:
            dim = dim_score.dimension
            dist = snapshot.get_distribution(dim, cohort.cohort_id)

            if cohort.privacy_suppressed or dist is None:
                results.append(DimensionBenchmarkResult(
                    dimension=dim,
                    normalized_score=dim_score.normalized_score,
                    percentile=None,
                    percentile_band=None,
                    reference_mean=None,
                    reference_p50=None,
                    confidence_level=ConfidenceLevel.INSUFFICIENT,
                    confidence_notes=["Sin datos de referencia disponibles para esta cohorte"],
                    cohort_id=cohort.cohort_id,
                    cohort_level=cohort.level,
                    effective_n=cohort.effective_n,
                    suppressed=True,
                ))
                continue

            percentile = self._interpolate_percentile(dim_score.normalized_score, dist.percentiles)
            confidence, notes = _confidence(dist.n_effective, self._privacy.min_effective_n_for_percentile, used_fallback)

            results.append(DimensionBenchmarkResult(
                dimension=dim,
                normalized_score=dim_score.normalized_score,
                percentile=round(percentile, 1),
                percentile_band=_percentile_band(percentile),
                reference_mean=dist.mean,
                reference_p50=dist.percentiles.get("p50"),
                confidence_level=confidence,
                confidence_notes=notes,
                cohort_id=cohort.cohort_id,
                cohort_level=cohort.level,
                effective_n=dist.n_effective,
                suppressed=False,
            ))

        return BenchmarkResult(
            response_id=scoring.response_id,
            snapshot_id=snapshot.snapshot_id,
            cohort_assignment=cohort,
            dimension_results=results,
        )

    @staticmethod
    def _interpolate_percentile(score: float, percentiles: dict[str, float]) -> float:
        """Interpola el percentil de un score dado el mapa p25/p50/p75/p90."""
        anchors = sorted(
            [(float(k[1:]), v) for k, v in percentiles.items()],
            key=lambda x: x[0],
        )
        if not anchors:
            return 50.0
        if score <= anchors[0][1]:
            return anchors[0][0] * score / anchors[0][1] if anchors[0][1] > 0 else 0.0
        if score >= anchors[-1][1]:
            excess = (score - anchors[-1][1]) / (1.0 - anchors[-1][1] + 1e-9)
            return min(100.0, anchors[-1][0] + excess * (100.0 - anchors[-1][0]))
        for i in range(len(anchors) - 1):
            lo_p, lo_v = anchors[i]
            hi_p, hi_v = anchors[i + 1]
            if lo_v <= score <= hi_v:
                if hi_v == lo_v:
                    return lo_p
                t = (score - lo_v) / (hi_v - lo_v)
                return lo_p + t * (hi_p - lo_p)
        return 50.0
