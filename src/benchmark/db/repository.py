"""
Repositorio — operaciones de persistencia para cada zona de datos.

Principios:
- Cada método es atómico dentro de su sesión.
- Idempotencia garantizada por idempotency_key (upsert seguro).
- Los resultados se persisten ANTES de responder al cliente (RNF-03).
- ContactStore nunca se une a consultas analíticas.
- Los agregados solo se crean desde jobs offline (no desde este módulo).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from benchmark.db.models import (
    AuditEventRecord,
    BenchmarkSnapshotRecord,
    CohortAssignmentRecord,
    ContactStore,
    DimensionScoreRecord,
    OperatorResultRecord,
    ResponseSessionRecord,
    AnswerRecord,
)
from benchmark.domain.models import (
    BenchmarkSnapshot,
    CohortAssignment,
    DimensionDistribution,
    DimensionId,
    OperatorReport,
    RawResponse,
    ScoringResult,
    SnapshotStatus,
    TopQuartilePractice,
    ValidationResult,
    ValidationStatus,
)

_CONTACT_RETENTION_DAYS = 90


# ── Zona 2: Respuestas pseudónimas ────────────────────────────────────────────

class ResponseRepository:

    def find_by_idempotency_key(
        self, session: Session, key: str
    ) -> ResponseSessionRecord | None:
        return session.scalar(
            select(ResponseSessionRecord).where(
                ResponseSessionRecord.idempotency_key == key
            )
        )

    def save_response(
        self,
        session: Session,
        response: RawResponse,
        validation: ValidationResult,
    ) -> ResponseSessionRecord:
        """
        Persiste la sesión, respuestas y resultado de validación.
        Los atributos de cohorte ya llegan como bandas desde la capa de aplicación.
        """
        record = ResponseSessionRecord(
            id=response.response_id,
            questionnaire_version=response.questionnaire_version,
            idempotency_key=response.idempotency_key,
            received_at=response.received_at,
            region_band=response.cohort_attributes.region,
            dc_type_band=response.cohort_attributes.dc_type,
            capacity_band=response.cohort_attributes.capacity_band,
            workload_band=response.cohort_attributes.primary_workload,
            validation_status=validation.status.value,
            quality_score=validation.quality_score,
            included_in_dataset=False,
        )
        session.add(record)

        for ans in response.answers:
            session.add(AnswerRecord(
                session_id=response.response_id,
                question_id=ans.question_id,
                option_id=ans.option_id,
            ))

        return record

    def save_scores(
        self,
        session: Session,
        scoring: ScoringResult,
    ) -> None:
        for ds in scoring.dimension_scores:
            session.add(DimensionScoreRecord(
                session_id=scoring.response_id,
                dimension=ds.dimension.value,
                raw_score=ds.raw_score,
                normalized_score=ds.normalized_score,
                max_possible=ds.max_possible,
                scoring_version=ds.scoring_version,
                blocker_types=ds.blocker_types,
                evidence=[e.model_dump() for e in ds.evidence],
            ))

    def save_cohort(
        self,
        session: Session,
        cohort: CohortAssignment,
    ) -> None:
        session.add(CohortAssignmentRecord(
            session_id=cohort.response_id,
            cohort_id=cohort.cohort_id,
            level=cohort.level,
            level_label=cohort.level_label,
            attributes_used=cohort.attributes_used,
            fallback_path=cohort.fallback_path,
            effective_n=cohort.effective_n,
            cohort_version=cohort.cohort_version,
            privacy_suppressed=cohort.privacy_suppressed,
        ))

    def mark_included_in_dataset(self, session: Session, response_id: str) -> None:
        record = session.get(ResponseSessionRecord, response_id)
        if record:
            record.included_in_dataset = True

    def get_valid_not_included(
        self, session: Session, limit: int = 1000
    ) -> list[ResponseSessionRecord]:
        """Devuelve respuestas válidas que aún no se incorporaron al dataset primario."""
        return list(session.scalars(
            select(ResponseSessionRecord)
            .where(
                ResponseSessionRecord.validation_status == ValidationStatus.VALID.value,
                ResponseSessionRecord.included_in_dataset == False,  # noqa: E712
            )
            .limit(limit)
        ))


# ── Zona 5: Snapshots y resultados ────────────────────────────────────────────

class SnapshotRepository:

    def get_active_snapshot(self, session: Session) -> BenchmarkSnapshot | None:
        """Carga el snapshot publicado más reciente."""
        record = session.scalar(
            select(BenchmarkSnapshotRecord)
            .where(BenchmarkSnapshotRecord.status == SnapshotStatus.PUBLISHED.value)
            .order_by(BenchmarkSnapshotRecord.published_at.desc())
            .limit(1)
        )
        if record is None:
            return None
        return _record_to_snapshot(record)

    def get_snapshot_by_id(self, session: Session, snapshot_id: str) -> BenchmarkSnapshot | None:
        record = session.get(BenchmarkSnapshotRecord, snapshot_id)
        if record is None:
            return None
        return _record_to_snapshot(record)

    def save_snapshot(
        self, session: Session, snapshot: BenchmarkSnapshot
    ) -> BenchmarkSnapshotRecord:
        record = BenchmarkSnapshotRecord(
            id=snapshot.snapshot_id,
            status=snapshot.status.value,
            questionnaire_version=snapshot.questionnaire_version,
            scoring_version=snapshot.scoring_version,
            cohort_version=snapshot.cohort_version,
            rebalancing_version=snapshot.rebalancing_version,
            published_at=snapshot.published_at,
            primary_data_cutoff=snapshot.primary_data_cutoff,
            distributions_json=_distributions_to_json(snapshot.distributions),
            top_quartile_practices_json=_practices_to_json(snapshot.top_quartile_practices),
            rebalancing_weights_json=snapshot.rebalancing_weights,
            privacy_thresholds_json=snapshot.privacy_thresholds,
            methodology_notes=snapshot.methodology_notes,
        )
        session.add(record)
        return record

    def publish_snapshot(
        self, session: Session, snapshot_id: str, approved_by: str
    ) -> None:
        """
        Publica un snapshot draft de forma atómica.
        Marca el snapshot anterior como superseded.
        """
        # Supersede el snapshot activo anterior
        prev = session.scalar(
            select(BenchmarkSnapshotRecord)
            .where(BenchmarkSnapshotRecord.status == SnapshotStatus.PUBLISHED.value)
        )
        if prev:
            prev.status = SnapshotStatus.SUPERSEDED.value

        # Publica el nuevo
        record = session.get(BenchmarkSnapshotRecord, snapshot_id)
        if record is None:
            raise ValueError(f"Snapshot {snapshot_id} no encontrado")
        if record.status != SnapshotStatus.DRAFT.value:
            raise ValueError(
                f"Solo se puede publicar un snapshot en estado draft (actual: {record.status})"
            )
        record.status = SnapshotStatus.PUBLISHED.value
        record.published_at = datetime.utcnow()
        record.approved_by = approved_by


class ResultRepository:

    def save_result(
        self, session: Session, report: OperatorReport
    ) -> OperatorResultRecord:
        record = OperatorResultRecord(
            id=report.result_id,
            session_id=report.response_id,
            snapshot_id=report.snapshot_id,
            generated_at=report.generated_at,
            questionnaire_version=report.questionnaire_version,
            scoring_version=report.scoring_version,
            cohort_version=report.cohort_version,
            rebalancing_version=report.rebalancing_version,
            report_json=report.model_dump(mode="json"),
        )
        session.add(record)
        return record

    def get_result_by_response_id(
        self, session: Session, response_id: str
    ) -> OperatorResultRecord | None:
        return session.scalar(
            select(OperatorResultRecord).where(
                OperatorResultRecord.session_id == response_id
            )
        )


# ── Zona 1: Contacto opcional ─────────────────────────────────────────────────

class ContactRepository:
    """
    Almacén de contacto completamente separado.
    No hay FK hacia tablas analíticas — la relación es solo lógica por hash.
    """

    def save_contact(
        self,
        session: Session,
        response_id: str,
        email: str,
    ) -> None:
        """
        Guarda el email cifrado. Usa un hash del response_id como referencia
        para que no sea posible hacer JOIN con la tabla analítica por accidente.
        """
        response_id_hash = hashlib.sha256(response_id.encode()).hexdigest()
        expires_at = datetime.utcnow() + timedelta(days=_CONTACT_RETENTION_DAYS)
        session.add(ContactStore(
            response_id_hash=response_id_hash,
            # En producción: cifrar con KMS o Fernet antes de guardar
            encrypted_email=_pseudonymize_email(email),
            expires_at=expires_at,
        ))

    def mark_delivered(self, session: Session, response_id: str) -> None:
        response_id_hash = hashlib.sha256(response_id.encode()).hexdigest()
        record = session.scalar(
            select(ContactStore).where(ContactStore.response_id_hash == response_id_hash)
        )
        if record:
            record.delivered = True

    def purge_expired(self, session: Session) -> int:
        """Elimina registros de contacto vencidos. Retorna el número eliminados."""
        expired = list(session.scalars(
            select(ContactStore).where(
                ContactStore.expires_at < datetime.utcnow(),
                ContactStore.deleted_at.is_(None),
            )
        ))
        for r in expired:
            r.deleted_at = datetime.utcnow()
        return len(expired)


# ── Auditoría ─────────────────────────────────────────────────────────────────

class AuditRepository:

    def log(
        self,
        session: Session,
        event_type: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        actor_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        session.add(AuditEventRecord(
            event_type=event_type,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_json=metadata or {},
        ))


# ── Helpers de serialización ──────────────────────────────────────────────────

def _distributions_to_json(distributions: list[DimensionDistribution]) -> dict:
    result: dict = {}
    for d in distributions:
        key = f"{d.dimension.value}::{d.cohort_id}"
        result[key] = {
            "dimension": d.dimension.value,
            "cohort_id": d.cohort_id,
            "percentiles": d.percentiles,
            "mean": d.mean,
            "std": d.std,
            "n_effective": d.n_effective,
            "top_quartile_threshold": d.top_quartile_threshold,
        }
    return result


def _practices_to_json(practices: list[TopQuartilePractice]) -> list[dict]:
    return [p.model_dump(mode="json") for p in practices]


def _record_to_snapshot(record: BenchmarkSnapshotRecord) -> BenchmarkSnapshot:
    distributions = [
        DimensionDistribution(
            dimension=DimensionId(v["dimension"]),
            cohort_id=v["cohort_id"],
            percentiles=v["percentiles"],
            mean=v["mean"],
            std=v["std"],
            n_effective=v["n_effective"],
            top_quartile_threshold=v["top_quartile_threshold"],
        )
        for v in record.distributions_json.values()
    ]
    practices = [
        TopQuartilePractice(
            dimension=DimensionId(p["dimension"]),
            cohort_id=p["cohort_id"],
            question_id=p["question_id"],
            option_id=p["option_id"],
            frequency_in_top=p["frequency_in_top"],
            frequency_in_rest=p["frequency_in_rest"],
            difference=p["difference"],
            statistical_support=p["statistical_support"],
        )
        for p in record.top_quartile_practices_json
    ]
    return BenchmarkSnapshot(
        snapshot_id=record.id,
        status=SnapshotStatus(record.status),
        published_at=record.published_at,
        questionnaire_version=record.questionnaire_version,
        scoring_version=record.scoring_version,
        cohort_version=record.cohort_version,
        rebalancing_version=record.rebalancing_version,
        primary_data_cutoff=record.primary_data_cutoff,
        distributions=distributions,
        top_quartile_practices=practices,
        rebalancing_weights=record.rebalancing_weights_json,
        privacy_thresholds=record.privacy_thresholds_json,
        methodology_notes=record.methodology_notes,
    )


def _pseudonymize_email(email: str) -> str:
    """
    Placeholder de pseudonimización.
    En producción reemplazar con cifrado simétrico (Fernet/KMS).
    Aquí devuelve el email tal cual para no bloquear el desarrollo.
    """
    return email
