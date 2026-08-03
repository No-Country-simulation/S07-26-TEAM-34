"""Fixtures compartidas de prueba. Sin datos sensibles."""
from __future__ import annotations

from benchmark.domain.models import (
    AnswerOptionConfig,
    BenchmarkSnapshot,
    CohortAttributes,
    CohortHierarchyConfig,
    CohortLevel,
    DimensionConfig,
    DimensionDistribution,
    DimensionId,
    PrivacyConfig,
    QuestionConfig,
    QuestionnaireConfig,
    RawAnswer,
    RawResponse,
    SnapshotStatus,
    TopQuartilePractice,
)


def make_questionnaire() -> QuestionnaireConfig:
    """Cuestionario mínimo para pruebas — 2 preguntas por dimensión."""
    dims = [
        DimensionConfig(id=d, name=d.value, description="")
        for d in DimensionId
    ]
    questions = []
    q_map = {
        DimensionId.VISIBILITY: ("q_vis_01", "q_vis_02"),
        DimensionId.FRICTION_ATTRIBUTION: ("q_fri_01", "q_fri_02"),
        DimensionId.COORDINATION_LATENCY: ("q_lat_01", "q_lat_02"),
        DimensionId.SELF_QUANTIFICATION: ("q_sq_01", "q_sq_02"),
        DimensionId.BLOCKERS: ("q_blk_01", "q_blk_02"),
    }
    for dim, (qid1, qid2) in q_map.items():
        is_blocker = dim == DimensionId.BLOCKERS
        for qid in (qid1, qid2):
            opts = [
                AnswerOptionConfig(id=f"{qid}_a", value=0, label="Ninguno",
                                   blocker_type="integration" if is_blocker else None),
                AnswerOptionConfig(id=f"{qid}_b", value=1, label="Bajo",
                                   blocker_type="ownership" if is_blocker else None),
                AnswerOptionConfig(id=f"{qid}_c", value=2, label="Medio",
                                   blocker_type="none" if is_blocker else None),
                AnswerOptionConfig(id=f"{qid}_d", value=3, label="Alto",
                                   blocker_type="none" if is_blocker else None),
            ]
            questions.append(QuestionConfig(
                id=qid,
                dimension=dim,
                text=f"Pregunta de prueba {qid}",
                weight=1.0,
                is_blocker=is_blocker,
                options=opts,
            ))
    return QuestionnaireConfig(
        version="1.0.0",
        published_at="2026-08-03",
        status="published",
        dimensions=dims,
        questions=questions,
        cohort_attributes=[],
    )


def make_full_response(version: str = "1.0.0", score_level: str = "high") -> RawResponse:
    """
    Respuesta completa con todas las preguntas.
    score_level: 'high' → opciones _d (3), 'low' → opciones _a (0), 'mid' → _b (1)
    """
    q = make_questionnaire()
    suffix = {"high": "_d", "low": "_a", "mid": "_b"}.get(score_level, "_d")
    answers = [RawAnswer(question_id=qc.id, option_id=f"{qc.id}{suffix}") for qc in q.questions]
    return RawResponse(
        response_id="test-response-001",
        questionnaire_version=version,
        answers=answers,
        cohort_attributes=CohortAttributes(
            region="latam", dc_type="colo", capacity_band="medium", primary_workload="general"
        ),
        idempotency_key="idem-001",
    )


def make_privacy_config() -> PrivacyConfig:
    return PrivacyConfig(
        version="1.0.0",
        min_cohort_size=5,
        min_top_quartile_support=5,
        min_effective_n_for_percentile=5,
    )


def make_cohort_hierarchy() -> CohortHierarchyConfig:
    return CohortHierarchyConfig(
        version="1.0.0",
        hierarchy=[
            CohortLevel(level=1, label="Región+Tipo+Capacidad+Workload",
                        attributes=["region", "dc_type", "capacity_band", "primary_workload"]),
            CohortLevel(level=2, label="Región+Tipo+Capacidad",
                        attributes=["region", "dc_type", "capacity_band"]),
            CohortLevel(level=3, label="Tipo+Capacidad",
                        attributes=["dc_type", "capacity_band"]),
            CohortLevel(level=4, label="Tipo",
                        attributes=["dc_type"]),
            CohortLevel(level=5, label="Global", attributes=[]),
        ],
    )


def make_snapshot_with_data(n_per_cohort: int = 20) -> BenchmarkSnapshot:
    """Snapshot con distribuciones y prácticas de prueba."""
    cohort_id = "capacity_band=medium|dc_type=colo|region=latam"
    distributions = []
    top_practices = []

    for dim in DimensionId:
        distributions.append(DimensionDistribution(
            dimension=dim,
            cohort_id=cohort_id,
            percentiles={"p25": 0.25, "p50": 0.50, "p75": 0.75, "p90": 0.88},
            mean=0.50,
            std=0.20,
            n_effective=n_per_cohort,
            top_quartile_threshold=0.75,
        ))
        distributions.append(DimensionDistribution(
            dimension=dim,
            cohort_id="global",
            percentiles={"p25": 0.20, "p50": 0.45, "p75": 0.70, "p90": 0.85},
            mean=0.45,
            std=0.22,
            n_effective=n_per_cohort * 5,
            top_quartile_threshold=0.70,
        ))

    # Una práctica top quartile por dimensión
    for dim in DimensionId:
        q_map = {
            DimensionId.VISIBILITY: "q_vis_01",
            DimensionId.FRICTION_ATTRIBUTION: "q_fri_01",
            DimensionId.COORDINATION_LATENCY: "q_lat_01",
            DimensionId.SELF_QUANTIFICATION: "q_sq_01",
            DimensionId.BLOCKERS: "q_blk_01",
        }
        top_practices.append(TopQuartilePractice(
            dimension=dim,
            cohort_id=cohort_id,
            question_id=q_map[dim],
            option_id=f"{q_map[dim]}_d",
            frequency_in_top=0.80,
            frequency_in_rest=0.20,
            difference=0.60,
            statistical_support=n_per_cohort,
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
