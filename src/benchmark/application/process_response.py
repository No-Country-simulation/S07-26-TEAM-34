"""
Caso de uso: procesar una respuesta de operador (flujo online).

Orquesta los motores en orden. Persiste el resultado en DB antes de responder.
El snapshot se fija al inicio — no cambia durante el procesamiento. (ADR-002, ADR-010)
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from benchmark.config.loader import (
    cached_cohort_hierarchy,
    cached_privacy_config,
    cached_questionnaire,
)
from benchmark.db.repository import (
    AuditRepository,
    ContactRepository,
    ResponseRepository,
    ResultRepository,
)
from benchmark.domain.models import (
    BenchmarkSnapshot,
    OperatorReport,
    RawResponse,
    ValidationStatus,
)
from benchmark.engines.benchmark import BenchmarkEngine
from benchmark.engines.cohort import CohortEngine
from benchmark.engines.interpretation import InterpretationEngine
from benchmark.engines.scoring import ScoringEngine
from benchmark.engines.top_quartile import TopQuartileEngine
from benchmark.engines.validation import ValidationEngine


@dataclass
class ProcessResponseResult:
    success: bool
    report: OperatorReport | None
    rejection_reason: str | None
    response_id: str


class ProcessResponseUseCase:
    """
    Flujo online completo:
    validación → scoring → cohorte → benchmark → top_quartile → interpretación → persistencia
    """

    def __init__(
        self,
        snapshot: BenchmarkSnapshot,
        result_id_factory,
        methodology_version: str = "1.0.0",
    ) -> None:
        # Fijar snapshot al inicio del caso de uso (ADR-002)
        self._snapshot = snapshot
        self._result_id_factory = result_id_factory
        self._version = methodology_version

        questionnaire = cached_questionnaire(methodology_version)
        cohort_hierarchy = cached_cohort_hierarchy(methodology_version)
        privacy = cached_privacy_config(methodology_version)

        self._validation = ValidationEngine(questionnaire)
        self._scoring = ScoringEngine(questionnaire)
        self._cohort = CohortEngine(cohort_hierarchy, privacy)
        self._benchmark = BenchmarkEngine(privacy)
        self._top_quartile = TopQuartileEngine(questionnaire, privacy)
        self._interpretation = InterpretationEngine(questionnaire)

        self._response_repo = ResponseRepository()
        self._result_repo = ResultRepository()
        self._contact_repo = ContactRepository()
        self._audit = AuditRepository()

    def execute(
        self,
        response: RawResponse,
        db: Session | None = None,
        contact_email: str | None = None,
    ) -> ProcessResponseResult:
        """
        Ejecuta el flujo completo.

        Si se pasa una sesión de DB (`db`), persiste todo en ella.
        Si no se pasa (tests unitarios), funciona en memoria.
        """
        # Idempotencia: si ya existe, retornar el resultado anterior
        if db is not None:
            existing = self._response_repo.find_by_idempotency_key(db, response.idempotency_key)
            if existing is not None:
                result_record = self._result_repo.get_result_by_response_id(db, existing.id)
                if result_record:
                    report = OperatorReport.model_validate(result_record.report_json)
                    return ProcessResponseResult(
                        success=True,
                        report=report,
                        rejection_reason=None,
                        response_id=existing.id,
                    )

        # 1. Validación — compuerta de entrada
        validation = self._validation.validate(response)

        if db is not None:
            self._response_repo.save_response(db, response, validation)
            self._audit.log(
                db,
                event_type="response.received",
                resource_type="response_session",
                resource_id=response.response_id,
                metadata={"status": validation.status.value, "quality": validation.quality_score},
            )

        if validation.status == ValidationStatus.REJECTED:
            reasons = "; ".join(e.message for e in validation.errors)
            return ProcessResponseResult(
                success=False,
                report=None,
                rejection_reason=reasons,
                response_id=response.response_id,
            )

        # 2. Scoring
        scoring = self._scoring.score(response, validation)

        # 3. Cohorte jerárquica con fallback
        cohort = self._cohort.assign(
            response.response_id,
            response.cohort_attributes,
            self._snapshot,
        )

        # 4. Benchmark (percentiles y confianza contra snapshot fijo)
        benchmark = self._benchmark.calculate(scoring, cohort, self._snapshot)

        # 5. Top quartile
        top_quartile = self._top_quartile.analyze(
            response, benchmark, self._snapshot, cohort
        )

        # 6. Interpretación y reporte final
        result_id = self._result_id_factory()
        report = self._interpretation.build_report(
            result_id=result_id,
            scoring=scoring,
            benchmark=benchmark,
            top_quartile=top_quartile,
            snapshot_id=self._snapshot.snapshot_id,
            rebalancing_version=self._snapshot.rebalancing_version,
        )

        # 7. Persistencia — antes de responder al cliente (RNF-03)
        if db is not None:
            self._response_repo.save_scores(db, scoring)
            self._response_repo.save_cohort(db, cohort)
            self._result_repo.save_result(db, report)

            # Contacto en almacén separado — nunca junto a datos analíticos
            if contact_email:
                self._contact_repo.save_contact(db, response.response_id, contact_email)

            self._audit.log(
                db,
                event_type="result.generated",
                resource_type="operator_result",
                resource_id=result_id,
                metadata={"snapshot_id": self._snapshot.snapshot_id},
            )

        return ProcessResponseResult(
            success=True,
            report=report,
            rejection_reason=None,
            response_id=response.response_id,
        )
