"""
ScoringEngine — convierte respuestas validadas en scores por dimensión. (RF-03)

Responsabilidad: aplicar reglas versionadas de la config para producir DimensionScores.
Sin dependencia de DB ni LLM. Determinista.

Invariantes:
- normalized_score siempre en [0.0, 1.0]
- mejorar una respuesta no puede reducir el score (monotonicidad)
- el mismo input + mismas reglas = mismo output
"""

from __future__ import annotations

from benchmark.domain.models import (
    AnswerEvidence,
    DimensionId,
    DimensionScore,
    QuestionnaireConfig,
    RawResponse,
    ScoringResult,
    ValidationResult,
    ValidationStatus,
)

_SCORING_VERSION = "1.0.0"


class ScoringEngine:
    """
    Motor de scoring. Sin estado — el mismo input siempre produce el mismo output.

    Precondición: la respuesta debe haber pasado ValidationEngine con status=VALID.
    """

    def __init__(self, questionnaire: QuestionnaireConfig) -> None:
        self._q = questionnaire

    def score(
        self,
        response: RawResponse,
        validation_result: ValidationResult,
    ) -> ScoringResult:
        if validation_result.status != ValidationStatus.VALID:
            raise ValueError(
                f"No se puede puntuar una respuesta inválida "
                f"(response_id={response.response_id}, "
                f"status={validation_result.status})"
            )

        # Indexar respuestas por question_id para acceso O(1)
        answers_by_question: dict[str, str] = {
            a.question_id: a.option_id for a in response.answers
        }

        dimension_scores = [
            self._score_dimension(dim, answers_by_question)
            for dim in DimensionId
        ]

        return ScoringResult(
            response_id=response.response_id,
            questionnaire_version=response.questionnaire_version,
            scoring_version=_SCORING_VERSION,
            dimension_scores=dimension_scores,
        )

    # ── privados ──────────────────────────────────────────────────────────────

    def _score_dimension(
        self,
        dim: DimensionId,
        answers_by_question: dict[str, str],
    ) -> DimensionScore:
        questions = self._q.questions_for_dimension(dim)
        evidence: list[AnswerEvidence] = []
        raw_score = 0.0
        max_possible = 0.0
        blocker_types: list[str] = []

        for question in questions:
            option_id = answers_by_question.get(question.id)
            if option_id is None:
                # Pregunta no respondida: contribuye 0, reduce max posible proporcionalmente
                # pero sí suma al max (penaliza la incompletitud)
                max_option_value = max((o.value for o in question.options), default=0.0)
                max_possible += max_option_value * question.weight
                continue

            option = self._q.get_option(question.id, option_id)
            if option is None:
                # No debería llegar aquí si pasó validación, pero defensive
                max_option_value = max((o.value for o in question.options), default=0.0)
                max_possible += max_option_value * question.weight
                continue

            weighted_contribution = option.value * question.weight
            raw_score += weighted_contribution
            max_option_value = max((o.value for o in question.options), default=0.0)
            max_possible += max_option_value * question.weight

            evidence.append(AnswerEvidence(
                question_id=question.id,
                option_id=option_id,
                raw_value=option.value,
                weight=question.weight,
                weighted_contribution=weighted_contribution,
            ))

            # Registrar blocker_type si aplica
            if question.is_blocker and option.blocker_type and option.blocker_type != "none":
                blocker_types.append(option.blocker_type)

        normalized = raw_score / max_possible if max_possible > 0 else 0.0
        normalized = round(min(1.0, max(0.0, normalized)), 6)

        return DimensionScore(
            dimension=dim,
            raw_score=round(raw_score, 6),
            normalized_score=normalized,
            max_possible=round(max_possible, 6),
            evidence=evidence,
            blocker_types=list(set(blocker_types)),
            scoring_version=_SCORING_VERSION,
        )
