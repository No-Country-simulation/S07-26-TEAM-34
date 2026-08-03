"""Tests unitarios y de propiedades — ScoringEngine."""
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.fixtures import make_full_response, make_questionnaire
from benchmark.domain.models import DimensionId, RawAnswer, ValidationResult, ValidationStatus
from benchmark.engines.scoring import ScoringEngine
from benchmark.engines.validation import ValidationEngine


@pytest.fixture
def engine():
    return ScoringEngine(make_questionnaire())


@pytest.fixture
def valid_result():
    q = make_questionnaire()
    response = make_full_response()
    val = ValidationEngine(q).validate(response)
    return response, val


def test_scores_in_range(engine, valid_result):
    response, val = valid_result
    result = engine.score(response, val)
    for ds in result.dimension_scores:
        assert 0.0 <= ds.normalized_score <= 1.0, f"Score fuera de rango: {ds}"


def test_all_dimensions_present(engine, valid_result):
    response, val = valid_result
    result = engine.score(response, val)
    dims = {ds.dimension for ds in result.dimension_scores}
    assert dims == set(DimensionId)


def test_high_score_greater_than_low(engine):
    q = make_questionnaire()
    val_engine = ValidationEngine(q)

    high_resp = make_full_response(score_level="high")
    low_resp = make_full_response(score_level="low")
    low_resp.response_id = "test-low"
    low_resp.idempotency_key = "idem-low"

    val_high = val_engine.validate(high_resp)
    val_low = val_engine.validate(low_resp)

    result_high = engine.score(high_resp, val_high)
    result_low = engine.score(low_resp, val_low)

    for dim in DimensionId:
        s_high = next(d.normalized_score for d in result_high.dimension_scores if d.dimension == dim)
        s_low = next(d.normalized_score for d in result_low.dimension_scores if d.dimension == dim)
        assert s_high >= s_low, f"Monotonicidad violada en {dim}: high={s_high} < low={s_low}"


def test_rejects_invalid_response(engine):
    q = make_questionnaire()
    response = make_full_response()
    rejected = ValidationResult(
        response_id=response.response_id,
        questionnaire_version="1.0.0",
        status=ValidationStatus.REJECTED,
        quality_score=0.0,
    )
    with pytest.raises(ValueError, match="inválida"):
        engine.score(response, rejected)


def test_determinism(engine, valid_result):
    """Mismo input → mismo output."""
    response, val = valid_result
    r1 = engine.score(response, val)
    r2 = engine.score(response, val)
    for d1, d2 in zip(r1.dimension_scores, r2.dimension_scores):
        assert d1.normalized_score == d2.normalized_score
        assert d1.raw_score == d2.raw_score


def test_evidence_sums_to_raw_score(engine, valid_result):
    """La suma de evidencias debe coincidir con raw_score."""
    response, val = valid_result
    result = engine.score(response, val)
    for ds in result.dimension_scores:
        evidence_sum = sum(e.weighted_contribution for e in ds.evidence)
        assert abs(evidence_sum - ds.raw_score) < 1e-5, (
            f"Evidencia no suma a raw_score en {ds.dimension}: "
            f"{evidence_sum} != {ds.raw_score}"
        )


def test_max_possible_geq_raw(engine, valid_result):
    response, val = valid_result
    result = engine.score(response, val)
    for ds in result.dimension_scores:
        assert ds.max_possible >= ds.raw_score


def test_blocker_types_captured(engine):
    """Las opciones con blocker_type != none se capturan en la dimensión blockers."""
    q = make_questionnaire()
    val_engine = ValidationEngine(q)
    response = make_full_response(score_level="low")  # opciones _a tienen blocker_type=integration
    val = val_engine.validate(response)
    result = engine.score(response, val)
    blockers = next(d for d in result.dimension_scores if d.dimension == DimensionId.BLOCKERS)
    assert "integration" in blockers.blocker_types


# ── Propiedades con Hypothesis ────────────────────────────────────────────────

@given(
    level=st.sampled_from(["high", "mid", "low"])
)
@settings(max_examples=30)
def test_property_scores_always_in_range(level):
    q = make_questionnaire()
    val_engine = ValidationEngine(q)
    scoring_engine = ScoringEngine(q)
    response = make_full_response(score_level=level)
    val = val_engine.validate(response)
    if val.is_valid:
        result = scoring_engine.score(response, val)
        for ds in result.dimension_scores:
            assert 0.0 <= ds.normalized_score <= 1.0
