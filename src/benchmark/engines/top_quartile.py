"""
TopQuartileEngine — identifica diferencias de prácticas entre el operador y el top 25%. (RF-06)

Solo publica prácticas con muestra suficiente y diferencia material. Sin causalidad implícita.
"""
from __future__ import annotations

from benchmark.domain.models import (
    BenchmarkResult,
    BenchmarkSnapshot,
    CohortAssignment,
    DimensionId,
    PrivacyConfig,
    QuestionnaireConfig,
    RawResponse,
    TopQuartileAnalysis,
    TopQuartileGap,
)

_MIN_DIFFERENCE = 0.15  # diferencia mínima en frecuencia para publicar una práctica


class TopQuartileEngine:
    def __init__(self, questionnaire: QuestionnaireConfig, privacy: PrivacyConfig) -> None:
        self._q = questionnaire
        self._privacy = privacy

    def analyze(
        self,
        response: RawResponse,
        benchmark_result: BenchmarkResult,
        snapshot: BenchmarkSnapshot,
        cohort: CohortAssignment,
    ) -> TopQuartileAnalysis:
        answers_by_q = {a.question_id: a.option_id for a in response.answers}
        gaps: list[TopQuartileGap] = []
        suppressed_dims: list[DimensionId] = []

        for dim_result in benchmark_result.dimension_results:
            dim = dim_result.dimension
            practices = snapshot.get_top_quartile_practices(dim, cohort.cohort_id)

            # Suprimir si no hay soporte suficiente
            if not practices or all(
                p.statistical_support < self._privacy.min_top_quartile_support
                for p in practices
            ):
                suppressed_dims.append(dim)
                continue

            # El operador ya está en el top quartile para esta dimensión: sin gaps
            if dim_result.percentile is not None and dim_result.percentile >= 75.0:
                continue

            for practice in practices:
                if practice.statistical_support < self._privacy.min_top_quartile_support:
                    continue
                if practice.difference < _MIN_DIFFERENCE:
                    continue

                operator_option_id = answers_by_q.get(practice.question_id)
                if operator_option_id == practice.option_id:
                    continue  # el operador ya tiene la práctica del top

                q_config = self._q.get_question(practice.question_id)
                if q_config is None:
                    continue

                op_option = self._q.get_option(practice.question_id, operator_option_id or "")
                top_option = self._q.get_option(
                    practice.question_id, practice.option_id
                )
                if top_option is None:
                    continue

                gaps.append(TopQuartileGap(
                    dimension=dim,
                    question_id=practice.question_id,
                    question_text=q_config.text,
                    operator_option_id=operator_option_id or "sin_respuesta",
                    operator_option_label=op_option.label if op_option else "Sin respuesta",
                    top_quartile_most_common_option_id=practice.option_id,
                    top_quartile_most_common_option_label=top_option.label,
                    gap_description=(
                        f"El {practice.frequency_in_top:.0%} de operadores del cuartil superior "
                        f"selecciona '{top_option.label}', frente al "
                        f"{practice.frequency_in_rest:.0%} en el resto del grupo."
                    ),
                    statistical_support=practice.statistical_support,
                ))

        return TopQuartileAnalysis(
            response_id=response.response_id,
            snapshot_id=snapshot.snapshot_id,
            cohort_id=cohort.cohort_id,
            gaps=gaps,
            suppressed_dimensions=suppressed_dims,
        )
