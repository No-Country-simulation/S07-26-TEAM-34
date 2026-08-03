"""
RebalancingEngine — calcula pesos dinámicos por dimensión y cohorte. (ADR-005, Fase 5)

Solo se ejecuta en el flujo offline al construir snapshots candidatos.
Invariante: peso_público + peso_primario = 1.0
Invariante: sin datos primarios válidos → peso_primario = 0.0
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass
class PrimaryDataMetrics:
    """Métricas del dataset primario para una dimensión y cohorte."""
    dimension: str
    cohort_id: str
    n_effective: int
    n_target: int           # tamaño objetivo mínimo para peso primario máximo
    quality_score: float    # [0,1] promedio ponderado de quality scores
    representativeness: float  # [0,1] cobertura de segmentos esperados
    recency_score: float    # [0,1] decaimiento por edad
    stability_score: float  # [0,1] variación entre ventanas (1=muy estable)


@dataclass
class RebalancingWeight:
    dimension: str
    cohort_id: str
    primary_weight: float
    public_weight: float
    factors: dict[str, float]
    rebalancing_version: str


class RebalancingEngine:
    """
    Calcula pesos usando media geométrica de 5 factores.
    Un factor débil no queda oculto por los demás.

    La función es saturante y monotónica: crece con la evidencia, nunca supera 1.
    """

    VERSION = "1.0.0"

    def calculate_weights(self, metrics: PrimaryDataMetrics) -> RebalancingWeight:
        factors = self._compute_factors(metrics)
        primary_weight = self._geometric_mean(list(factors.values()))
        primary_weight = round(min(1.0, max(0.0, primary_weight)), 6)
        public_weight = round(1.0 - primary_weight, 6)

        return RebalancingWeight(
            dimension=metrics.dimension,
            cohort_id=metrics.cohort_id,
            primary_weight=primary_weight,
            public_weight=public_weight,
            factors=factors,
            rebalancing_version=self.VERSION,
        )

    def calculate_weights_batch(
        self, metrics_list: list[PrimaryDataMetrics]
    ) -> list[RebalancingWeight]:
        return [self.calculate_weights(m) for m in metrics_list]

    # ── privados ──────────────────────────────────────────────────────────────

    def _compute_factors(self, m: PrimaryDataMetrics) -> dict[str, float]:
        sufficiency = min(1.0, m.n_effective / m.n_target) if m.n_target > 0 else 0.0
        return {
            "sufficiency":       round(sufficiency, 4),
            "quality":           round(min(1.0, max(0.0, m.quality_score)), 4),
            "representativeness": round(min(1.0, max(0.0, m.representativeness)), 4),
            "recency":           round(min(1.0, max(0.0, m.recency_score)), 4),
            "stability":         round(min(1.0, max(0.0, m.stability_score)), 4),
        }

    @staticmethod
    def _geometric_mean(values: list[float]) -> float:
        if not values or any(v <= 0 for v in values):
            return 0.0
        log_sum = sum(math.log(v) for v in values)
        return math.exp(log_sum / len(values))
