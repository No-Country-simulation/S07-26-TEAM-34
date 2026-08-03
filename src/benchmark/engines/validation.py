"""
ValidationEngine — compuerta de entrada del benchmark. (ADR-003)

Responsabilidad: determinar si una respuesta puede puntuar y alimentar el dataset.
Sin dependencia de DB ni LLM. Determinista.

Salida: ValidationResult con status, errores bloqueantes, advertencias y quality_score.
Una respuesta con status=REJECTED no puede alimentar scores publicados ni el dataset primario.
"""

from __future__ import annotations

from benchmark.domain.models import (
    QuestionnaireConfig,
    RawAnswer,
    RawResponse,
    ValidationError,
    ValidationResult,
    ValidationStatus,
    ValidationWarning,
)

# Umbral de completitud mínima para que una respuesta sea válida
_MIN_COMPLETENESS = 0.8


class ValidationEngine:
    """
    Motor de validación. Sin estado — el mismo input siempre produce el mismo output.

    Reglas (en orden de prioridad):
    1. Versión de cuestionario publicada y reconocida.
    2. No existen preguntas desconocidas en las respuestas.
    3. No existen opciones desconocidas para una pregunta dada.
    4. Completitud mínima por dimensión y total.
    5. No hay respuestas duplicadas para la misma pregunta.
    6. Advertencias no bloqueantes: respuestas inesperadas.
    """

    def __init__(self, questionnaire: QuestionnaireConfig) -> None:
        self._q = questionnaire

    def validate(self, response: RawResponse) -> ValidationResult:
        errors: list[ValidationError] = []
        warnings: list[ValidationWarning] = []

        # 1. Versión reconocida
        if response.questionnaire_version != self._q.version:
            errors.append(ValidationError(
                code="VERSION_MISMATCH",
                message=(
                    f"Versión de cuestionario '{response.questionnaire_version}' "
                    f"no coincide con la config cargada '{self._q.version}'"
                ),
            ))
            return self._build_result(response, errors, warnings, quality_score=0.0)

        # 2. Detectar preguntas desconocidas
        known_ids = {q.id for q in self._q.questions}
        answered_ids: list[str] = []
        for ans in response.answers:
            if ans.question_id not in known_ids:
                errors.append(ValidationError(
                    code="UNKNOWN_QUESTION",
                    question_id=ans.question_id,
                    message=f"Pregunta desconocida: {ans.question_id}",
                ))
            else:
                answered_ids.append(ans.question_id)

        # 3. Opciones desconocidas
        for ans in response.answers:
            q_config = self._q.get_question(ans.question_id)
            if q_config is None:
                continue  # ya capturado arriba
            known_options = {o.id for o in q_config.options}
            if ans.option_id not in known_options:
                errors.append(ValidationError(
                    code="UNKNOWN_OPTION",
                    question_id=ans.question_id,
                    message=(
                        f"Opción '{ans.option_id}' no reconocida "
                        f"para pregunta '{ans.question_id}'"
                    ),
                ))

        # 4. Duplicados
        seen: dict[str, int] = {}
        for ans in response.answers:
            seen[ans.question_id] = seen.get(ans.question_id, 0) + 1
        for qid, count in seen.items():
            if count > 1:
                errors.append(ValidationError(
                    code="DUPLICATE_ANSWER",
                    question_id=qid,
                    message=f"Pregunta '{qid}' respondida {count} veces",
                ))

        # Si hay errores bloqueantes no continuamos con completitud
        if errors:
            return self._build_result(response, errors, warnings, quality_score=0.0)

        # 5. Completitud total
        total_questions = len(self._q.questions)
        answered_set = {a.question_id for a in response.answers}
        completeness = len(answered_set) / total_questions if total_questions > 0 else 0.0

        if completeness < _MIN_COMPLETENESS:
            errors.append(ValidationError(
                code="INSUFFICIENT_COMPLETENESS",
                message=(
                    f"Completitud {completeness:.0%} inferior al mínimo "
                    f"requerido {_MIN_COMPLETENESS:.0%} "
                    f"({len(answered_set)}/{total_questions} preguntas respondidas)"
                ),
            ))

        # 6. Completitud por dimensión (advertencia si falta alguna dimensión completa)
        from benchmark.domain.models import DimensionId
        for dim in DimensionId:
            dim_questions = self._q.questions_for_dimension(dim)
            if not dim_questions:
                continue
            dim_answered = sum(1 for q in dim_questions if q.id in answered_set)
            dim_completeness = dim_answered / len(dim_questions)
            if dim_completeness == 0.0:
                warnings.append(ValidationWarning(
                    code="DIMENSION_NOT_ANSWERED",
                    message=f"Dimensión '{dim.value}' sin ninguna respuesta",
                ))
            elif dim_completeness < _MIN_COMPLETENESS:
                warnings.append(ValidationWarning(
                    code="DIMENSION_LOW_COMPLETENESS",
                    message=(
                        f"Dimensión '{dim.value}' con completitud baja "
                        f"({dim_completeness:.0%})"
                    ),
                ))

        quality_score = self._compute_quality_score(
            completeness=completeness,
            n_warnings=len(warnings),
        )

        return self._build_result(response, errors, warnings, quality_score)

    # ── privados ──────────────────────────────────────────────────────────────

    @staticmethod
    def _build_result(
        response: RawResponse,
        errors: list[ValidationError],
        warnings: list[ValidationWarning],
        quality_score: float,
    ) -> ValidationResult:
        status = ValidationStatus.VALID if not errors else ValidationStatus.REJECTED
        return ValidationResult(
            response_id=response.response_id,
            questionnaire_version=response.questionnaire_version,
            status=status,
            errors=errors,
            warnings=warnings,
            quality_score=quality_score,
        )

    @staticmethod
    def _compute_quality_score(completeness: float, n_warnings: int) -> float:
        """
        Quality score entre 0.0 y 1.0.
        Base: completitud. Penalización: 0.05 por advertencia, mínimo 0.
        """
        penalty = min(n_warnings * 0.05, 0.3)
        return max(0.0, round(completeness - penalty, 4))
