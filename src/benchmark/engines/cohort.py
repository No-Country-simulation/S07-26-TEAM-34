"""
CohortEngine — selecciona el grupo comparable con fallback jerárquico. (ADR-006, RF-04)

Responsabilidad: dado un conjunto de atributos de cohorte y un snapshot,
seleccionar el nivel más específico que cumpla el tamaño efectivo mínimo.

Sin dependencia de DB ni LLM. Determinista.
"""

from __future__ import annotations

from benchmark.domain.models import (
    BenchmarkSnapshot,
    CohortAssignment,
    CohortAttributes,
    CohortHierarchyConfig,
    DimensionId,
    PrivacyConfig,
)

_COHORT_VERSION = "1.0.0"


def _build_cohort_id(attributes: dict[str, str]) -> str:
    """Genera un ID de cohorte canónico y ordenado."""
    if not attributes:
        return "global"
    return "|".join(f"{k}={v}" for k, v in sorted(attributes.items()))


class CohortEngine:
    """
    Motor de cohortes. Sin estado.

    Selecciona la cohorte más específica disponible en el snapshot que:
    1. Tiene datos en el snapshot (n_effective > 0).
    2. Cumple min_effective_n del config de privacidad.

    Registra el camino de fallback en CohortAssignment.
    """

    def __init__(
        self,
        hierarchy: CohortHierarchyConfig,
        privacy: PrivacyConfig,
    ) -> None:
        self._hierarchy = hierarchy
        self._privacy = privacy

    def assign(
        self,
        response_id: str,
        cohort_attributes: CohortAttributes,
        snapshot: BenchmarkSnapshot,
    ) -> CohortAssignment:
        attrs_dict = cohort_attributes.as_dict()
        fallback_path: list[int] = []

        for level_config in sorted(self._hierarchy.hierarchy, key=lambda l: l.level):
            # Filtrar atributos del operador al subconjunto de este nivel
            level_attrs = {
                k: v for k, v in attrs_dict.items()
                if k in level_config.attributes
            }
            cohort_id = _build_cohort_id(level_attrs)

            # Calcular n_effective de este cohort_id en el snapshot
            # (mínimo n_effective sobre todas las dimensiones disponibles)
            n_effective = self._min_effective_n_in_snapshot(snapshot, cohort_id)

            if n_effective >= self._privacy.min_cohort_size:
                return CohortAssignment(
                    response_id=response_id,
                    cohort_id=cohort_id,
                    level=level_config.level,
                    level_label=level_config.label,
                    attributes_used=level_attrs,
                    fallback_path=fallback_path,
                    effective_n=n_effective,
                    cohort_version=_COHORT_VERSION,
                    privacy_suppressed=False,
                )

            fallback_path.append(level_config.level)

        # Ningún nivel superó el umbral: resultado suprimido por privacidad
        return CohortAssignment(
            response_id=response_id,
            cohort_id="suppressed",
            level=0,
            level_label="Suprimido por privacidad",
            attributes_used={},
            fallback_path=fallback_path,
            effective_n=0,
            cohort_version=_COHORT_VERSION,
            privacy_suppressed=True,
        )

    # ── privados ──────────────────────────────────────────────────────────────

    @staticmethod
    def _min_effective_n_in_snapshot(
        snapshot: BenchmarkSnapshot,
        cohort_id: str,
    ) -> int:
        """
        Devuelve el mínimo n_effective de este cohort_id entre todas las dimensiones.
        Si no hay ninguna distribución para este cohort_id devuelve 0.
        """
        ns = [
            d.n_effective
            for d in snapshot.distributions
            if d.cohort_id == cohort_id
        ]
        return min(ns) if ns else 0
