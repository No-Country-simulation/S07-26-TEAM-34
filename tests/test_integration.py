"""
Tests de integración — flujo online completo.

Usa el cuestionario real del YAML (20 preguntas) para verificar el flujo end-to-end.
Verifica: reproducibilidad, rechazo de inválidas, versionado, cohortes y top quartile.
"""
import uuid
import pytest

from tests.fixtures import make_privacy_config, make_snapshot_with_data
from benchmark.application.process_response import ProcessResponseUseCase
from benchmark.config.loader import cached_questionnaire
from benchmark.domain.models import CohortAttributes, DimensionId, RawAnswer, RawResponse


def _full_response_from_yaml(version: str = "1.0.0", score_level: str = "high") -> RawResponse:
    """Respuesta completa usando las preguntas reales del YAML."""
    q = cached_questionnaire(version)
    suffix_map = {"high": 3, "mid": 1, "low": 0}
    opt_index = suffix_map.get(score_level, 3)
    answers = []
    for question in q.questions:
        option = question.options[min(opt_index, len(question.options) - 1)]
        answers.append(RawAnswer(question_id=question.id, option_id=option.id))
    return RawResponse(
        response_id=str(uuid.uuid4()),
        questionnaire_version=version,
        answers=answers,
        cohort_attributes=CohortAttributes(
            region="latam", dc_type="colo", capacity_band="medium", primary_workload="general"
        ),
        idempotency_key=str(uuid.uuid4()),
    )


def _make_snapshot():
    """Snapshot con datos para el cohort_id que produce el operador de prueba."""
    from benchmark.domain.models import (
        BenchmarkSnapshot, DimensionDistribution, SnapshotStatus, TopQuartilePractice
    )
    cohort_id = "capacity_band=medium|dc_type=colo|region=latam"
    distributions = []
    top_practices = []
    q = cached_questionnaire("1.0.0")

    dim_first_q = {
        DimensionId.VISIBILITY: "q_vis_01",
        DimensionId.FRICTION_ATTRIBUTION: "q_fri_01",
        DimensionId.COORDINATION_LATENCY: "q_lat_01",
        DimensionId.SELF_QUANTIFICATION: "q_sq_01",
        DimensionId.BLOCKERS: "q_blk_01",
    }

    for dim in DimensionId:
        for cid in [cohort_id, "global"]:
            n = 20 if cid == cohort_id else 100
            distributions.append(DimensionDistribution(
                dimension=dim, cohort_id=cid,
                percentiles={"p25": 0.25, "p50": 0.50, "p75": 0.75, "p90": 0.88},
                mean=0.50, std=0.20, n_effective=n,
                top_quartile_threshold=0.75,
            ))
        qid = dim_first_q[dim]
        qconfig = q.get_question(qid)
        if qconfig:
            top_option = qconfig.options[-1]  # opción de mayor valor
            top_practices.append(TopQuartilePractice(
                dimension=dim, cohort_id=cohort_id,
                question_id=qid,
                option_id=top_option.id,
                frequency_in_top=0.80,
                frequency_in_rest=0.20,
                difference=0.60,
                statistical_support=20,
            ))

    return BenchmarkSnapshot(
        snapshot_id="test-snapshot-001",
        status=SnapshotStatus.PUBLISHED,
        published_at=None,
        questionnaire_version="1.0.0",
        scoring_version="1.0.0",
        cohort_version="1.0.0",
        rebalancing_version="1.0.0",
        primary_data_cutoff=None,
        distributions=distributions,
        top_quartile_practices=top_practices,
    )


@pytest.fixture
def use_case():
    snapshot = _make_snapshot()
    return ProcessResponseUseCase(
        snapshot=snapshot,
        result_id_factory=lambda: str(uuid.uuid4()),
        methodology_version="1.0.0",
    )


def test_valid_response_produces_report(use_case):
    response = _full_response_from_yaml(score_level="mid")
    result = use_case.execute(response)
    assert result.success, f"Rechazado: {result.rejection_reason}"
    assert result.report is not None
    assert result.rejection_reason is None


def test_invalid_response_does_not_produce_report(use_case):
    response = _full_response_from_yaml()
    response.answers = []  # sin respuestas → completitud 0%
    result = use_case.execute(response)
    assert not result.success
    assert result.report is None
    assert result.rejection_reason is not None


def test_reproducibility(use_case):
    """El mismo nivel de respuesta produce el mismo score (determinismo)."""
    r1 = _full_response_from_yaml(score_level="mid")
    r2 = _full_response_from_yaml(score_level="mid")

    out1 = use_case.execute(r1)
    out2 = use_case.execute(r2)

    assert out1.success and out2.success
    for d1, d2 in zip(out1.report.dimension_results, out2.report.dimension_results):
        assert d1.dimension == d2.dimension
        assert d1.normalized_score == d2.normalized_score


def test_report_contains_all_dimensions(use_case):
    response = _full_response_from_yaml(score_level="high")
    result = use_case.execute(response)
    assert result.success, f"Rechazado: {result.rejection_reason}"
    dims = {dr.dimension for dr in result.report.dimension_results}
    assert dims == set(DimensionId)


def test_report_has_friction_profile(use_case):
    response = _full_response_from_yaml(score_level="low")
    result = use_case.execute(response)
    assert result.success, f"Rechazado: {result.rejection_reason}"
    assert result.report.friction_profile is not None
    assert result.report.friction_profile.primary_dimension is not None


def test_version_info_recorded(use_case):
    """Cada resultado registra las versiones metodológicas que lo produjeron."""
    response = _full_response_from_yaml()
    result = use_case.execute(response)
    assert result.success, f"Rechazado: {result.rejection_reason}"
    rep = result.report
    assert rep.questionnaire_version == "1.0.0"
    assert rep.scoring_version == "1.0.0"
    assert rep.snapshot_id == "test-snapshot-001"


def test_high_score_in_top_quartile_has_no_gaps(use_case):
    """Operador con score alto (opciones máximas) está en top quartile → sin gaps."""
    response = _full_response_from_yaml(score_level="high")
    result = use_case.execute(response)
    assert result.success, f"Rechazado: {result.rejection_reason}"
    assert len(result.report.top_quartile_analysis.gaps) == 0


def test_low_score_produces_gaps(use_case):
    """Operador con scores bajos tiene gaps con el top quartile."""
    response = _full_response_from_yaml(score_level="low")
    result = use_case.execute(response)
    assert result.success, f"Rechazado: {result.rejection_reason}"
    assert len(result.report.top_quartile_analysis.gaps) > 0


def test_cohort_level_recorded(use_case):
    """La cohorte usada y su nivel quedan registrados en el reporte."""
    response = _full_response_from_yaml()
    result = use_case.execute(response)
    assert result.success
    cohort = result.report.cohort_assignment
    assert cohort.cohort_id != "suppressed"
    assert cohort.level >= 1


def test_executive_summary_not_empty(use_case):
    response = _full_response_from_yaml(score_level="mid")
    result = use_case.execute(response)
    assert result.success
    assert len(result.report.executive_summary) > 20
