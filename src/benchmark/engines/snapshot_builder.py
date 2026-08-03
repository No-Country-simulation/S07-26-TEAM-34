"""
SnapshotBuilder — construye snapshots de benchmark desde datos públicos/primarios. (ADR-002, ADR-010)

Se ejecuta SOLO en el flujo offline. Nunca durante una solicitud de operador.
El snapshot resultante es inmutable una vez publicado.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np

from benchmark.domain.models import (
    BenchmarkSnapshot,
    CohortHierarchyConfig,
    DimensionDistribution,
    DimensionId,
    PrivacyConfig,
    QuestionnaireConfig,
    SnapshotStatus,
    TopQuartilePractice,
)

_SNAPSHOT_VERSION = "1.0.0"
_TOP_QUARTILE_THRESHOLD = 0.75   # percentil 75
_MIN_PRACTICE_DIFFERENCE = 0.15  # diferencia mínima de frecuencia


def _cohort_id_from_attrs(attrs: dict[str, str]) -> str:
    if not attrs:
        return "global"
    return "|".join(f"{k}={v}" for k, v in sorted(attrs.items()))


class SnapshotBuilder:
    """
    Construye un BenchmarkSnapshot desde un conjunto de registros analíticos.

    Parámetro `records`: lista de dicts con:
        - scores por dimensión (normalized_score)
        - atributos de cohorte (ya en bandas)
        - answers por question_id
        - quality_score
    """

    def __init__(
        self,
        questionnaire: QuestionnaireConfig,
        hierarchy: CohortHierarchyConfig,
        privacy: PrivacyConfig,
    ) -> None:
        self._q = questionnaire
        self._hierarchy = hierarchy
        self._privacy = privacy

    def build(
        self,
        snapshot_id: str,
        records: list[dict[str, Any]],
        rebalancing_version: str = "1.0.0",
        notes: str = "",
    ) -> BenchmarkSnapshot:
        distributions: list[DimensionDistribution] = []
        top_quartile_practices: list[TopQuartilePractice] = []

        cohort_groups = self._group_by_cohorts(records)

        for cohort_id, cohort_records in cohort_groups.items():
            n = len(cohort_records)
            if n < self._privacy.min_cohort_size:
                continue  # suprimir cohortes pequeñas

            for dim in DimensionId:
                scores = [
                    r["scores"][dim.value]
                    for r in cohort_records
                    if dim.value in r.get("scores", {})
                ]
                if len(scores) < self._privacy.min_cohort_size:
                    continue

                arr = np.array(scores, dtype=float)
                dist = DimensionDistribution(
                    dimension=dim,
                    cohort_id=cohort_id,
                    percentiles={
                        "p25": float(np.percentile(arr, 25)),
                        "p50": float(np.percentile(arr, 50)),
                        "p75": float(np.percentile(arr, 75)),
                        "p90": float(np.percentile(arr, 90)),
                    },
                    mean=float(np.mean(arr)),
                    std=float(np.std(arr)),
                    n_effective=n,
                    top_quartile_threshold=float(np.percentile(arr, 75)),
                )
                distributions.append(dist)

                # Prácticas top quartile
                top_threshold = dist.top_quartile_threshold
                top_records = [r for r in cohort_records if r.get("scores", {}).get(dim.value, 0) >= top_threshold]
                rest_records = [r for r in cohort_records if r.get("scores", {}).get(dim.value, 0) < top_threshold]

                if (
                    len(top_records) >= self._privacy.min_top_quartile_support
                    and len(rest_records) >= self._privacy.min_top_quartile_support
                ):
                    practices = self._extract_practices(dim, top_records, rest_records, cohort_id)
                    top_quartile_practices.extend(practices)

        return BenchmarkSnapshot(
            snapshot_id=snapshot_id,
            status=SnapshotStatus.DRAFT,
            published_at=None,
            questionnaire_version=self._q.version,
            scoring_version=_SNAPSHOT_VERSION,
            cohort_version=_SNAPSHOT_VERSION,
            rebalancing_version=rebalancing_version,
            primary_data_cutoff=datetime.utcnow(),
            distributions=distributions,
            top_quartile_practices=top_quartile_practices,
            methodology_notes=notes,
        )

    def _group_by_cohorts(self, records: list[dict]) -> dict[str, list[dict]]:
        """Agrupa registros por cada nivel de la jerarquía de cohortes."""
        groups: dict[str, list[dict]] = {"global": []}
        for record in records:
            groups["global"].append(record)
            attrs = record.get("cohort_attributes", {})
            for level in self._hierarchy.hierarchy:
                level_attrs = {k: v for k, v in attrs.items() if k in level.attributes}
                cid = _cohort_id_from_attrs(level_attrs)
                if cid != "global":
                    groups.setdefault(cid, []).append(record)
        return groups

    def _extract_practices(
        self,
        dim: DimensionId,
        top_records: list[dict],
        rest_records: list[dict],
        cohort_id: str,
    ) -> list[TopQuartilePractice]:
        practices: list[TopQuartilePractice] = []
        dim_questions = self._q.questions_for_dimension(dim)

        for question in dim_questions:
            qid = question.id
            top_answers = [r.get("answers", {}).get(qid) for r in top_records if r.get("answers", {}).get(qid)]
            rest_answers = [r.get("answers", {}).get(qid) for r in rest_records if r.get("answers", {}).get(qid)]

            if not top_answers:
                continue

            # Opción más frecuente en el top
            from collections import Counter
            top_counter = Counter(top_answers)
            most_common_option, top_count = top_counter.most_common(1)[0]
            freq_top = top_count / len(top_answers)

            rest_counter = Counter(rest_answers)
            rest_count = rest_counter.get(most_common_option, 0)
            freq_rest = rest_count / len(rest_answers) if rest_answers else 0.0
            difference = freq_top - freq_rest

            if difference < _MIN_PRACTICE_DIFFERENCE:
                continue

            practices.append(TopQuartilePractice(
                dimension=dim,
                cohort_id=cohort_id,
                question_id=qid,
                option_id=most_common_option,
                frequency_in_top=round(freq_top, 3),
                frequency_in_rest=round(freq_rest, 3),
                difference=round(difference, 3),
                statistical_support=len(top_answers),
            ))

        return practices
