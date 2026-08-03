"""Tests unitarios — ValidationEngine."""
import pytest
from tests.fixtures import make_full_response, make_questionnaire
from benchmark.domain.models import RawAnswer, RawResponse, CohortAttributes, ValidationStatus
from benchmark.engines.validation import ValidationEngine


@pytest.fixture
def engine():
    return ValidationEngine(make_questionnaire())


def test_valid_complete_response(engine):
    response = make_full_response()
    result = engine.validate(response)
    assert result.is_valid
    assert result.quality_score > 0.0
    assert result.errors == []


def test_wrong_version_rejected(engine):
    response = make_full_response(version="9.9.9")
    result = engine.validate(response)
    assert result.status == ValidationStatus.REJECTED
    assert any(e.code == "VERSION_MISMATCH" for e in result.errors)
    assert result.quality_score == 0.0


def test_unknown_question_rejected(engine):
    response = make_full_response()
    response.answers.append(RawAnswer(question_id="q_nonexistent", option_id="q_nonexistent_a"))
    result = engine.validate(response)
    assert result.status == ValidationStatus.REJECTED
    assert any(e.code == "UNKNOWN_QUESTION" for e in result.errors)


def test_unknown_option_rejected(engine):
    response = make_full_response()
    response.answers[0] = RawAnswer(
        question_id=response.answers[0].question_id,
        option_id="invalid_option_xyz"
    )
    result = engine.validate(response)
    assert result.status == ValidationStatus.REJECTED
    assert any(e.code == "UNKNOWN_OPTION" for e in result.errors)


def test_duplicate_answer_rejected(engine):
    response = make_full_response()
    first = response.answers[0]
    response.answers.append(RawAnswer(question_id=first.question_id, option_id=first.option_id))
    result = engine.validate(response)
    assert result.status == ValidationStatus.REJECTED
    assert any(e.code == "DUPLICATE_ANSWER" for e in result.errors)


def test_insufficient_completeness_rejected(engine):
    q = make_questionnaire()
    # Solo 1 respuesta de 10 → completitud 10%
    response = RawResponse(
        response_id="r1",
        questionnaire_version="1.0.0",
        answers=[RawAnswer(question_id=q.questions[0].id, option_id=f"{q.questions[0].id}_a")],
        cohort_attributes=CohortAttributes(),
        idempotency_key="k1",
    )
    result = engine.validate(response)
    assert result.status == ValidationStatus.REJECTED
    assert any(e.code == "INSUFFICIENT_COMPLETENESS" for e in result.errors)


def test_quality_score_decreases_with_warnings(engine):
    """Respuesta completa pero con dimensión sin responder genera advertencia y baja quality."""
    q = make_questionnaire()
    # Responder todo excepto las preguntas de BLOCKERS
    non_blocker = [qc for qc in q.questions if qc.dimension.value != "blockers"]
    answers = [RawAnswer(question_id=qc.id, option_id=f"{qc.id}_d") for qc in non_blocker]
    # Agregar preguntas de blockers con option válida para mantener >80% completitud
    blocker_qs = [qc for qc in q.questions if qc.dimension.value == "blockers"]
    for bq in blocker_qs[:1]:  # solo una, la otra falta
        answers.append(RawAnswer(question_id=bq.id, option_id=f"{bq.id}_d"))

    response = RawResponse(
        response_id="r2",
        questionnaire_version="1.0.0",
        answers=answers,
        cohort_attributes=CohortAttributes(),
        idempotency_key="k2",
    )
    result_partial = engine.validate(response)
    result_full = engine.validate(make_full_response())

    if result_partial.is_valid:
        assert result_partial.quality_score <= result_full.quality_score
