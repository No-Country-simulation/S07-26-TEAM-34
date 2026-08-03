"""
Tests de Fase 4 — persistencia, privacidad e idempotencia.

Usan SQLite en memoria para no depender de PostgreSQL.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from benchmark.db.base import Base
from benchmark.db.models import (
    AnswerRecord,
    AuditEventRecord,
    BenchmarkSnapshotRecord,
    CohortAssignmentRecord,
    ContactStore,
    DimensionScoreRecord,
    OperatorResultRecord,
    ResponseSessionRecord,
)
from benchmark.db.repository import (
    AuditRepository,
    ContactRepository,
    ResponseRepository,
    ResultRepository,
    SnapshotRepository,
)
from benchmark.application.process_response import ProcessResponseUseCase
from benchmark.domain.models import CohortAttributes, RawAnswer, RawResponse, SnapshotStatus
from benchmark.config.loader import cached_questionnaire


# ── Fixture: DB en memoria ────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def db() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def set_pragma(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def _make_snapshot_record(session: Session) -> BenchmarkSnapshotRecord:
    record = BenchmarkSnapshotRecord(
        id="snap-001",
        status=SnapshotStatus.PUBLISHED.value,
        questionnaire_version="1.0.0",
        scoring_version="1.0.0",
        cohort_version="1.0.0",
        rebalancing_version="1.0.0",
        published_at=datetime.utcnow(),
        distributions_json={},
        top_quartile_practices_json=[],
        rebalancing_weights_json={},
        privacy_thresholds_json={},
    )
    session.add(record)
    session.commit()
    return record


def _full_response(version: str = "1.0.0") -> RawResponse:
    q = cached_questionnaire(version)
    answers = [
        RawAnswer(question_id=qc.id, option_id=qc.options[-1].id)
        for qc in q.questions
    ]
    return RawResponse(
        response_id=str(uuid.uuid4()),
        questionnaire_version=version,
        answers=answers,
        cohort_attributes=CohortAttributes(
            region="latam", dc_type="colo", capacity_band="medium", primary_workload="general"
        ),
        idempotency_key=str(uuid.uuid4()),
    )


# ── Tests de persistencia básica ──────────────────────────────────────────────

def test_response_persisted(db):
    from benchmark.engines.validation import ValidationEngine
    from benchmark.db.repository import ResponseRepository

    q = cached_questionnaire("1.0.0")
    response = _full_response()
    val = ValidationEngine(q).validate(response)

    repo = ResponseRepository()
    _make_snapshot_record(db)
    repo.save_response(db, response, val)
    db.commit()

    found = db.get(ResponseSessionRecord, response.response_id)
    assert found is not None
    assert found.validation_status == "valid"
    assert found.region_band == "latam"
    assert found.capacity_band == "medium"


def test_answers_persisted_without_pii(db):
    """Las respuestas se guardan pero sin datos de identificación del operador."""
    from benchmark.engines.validation import ValidationEngine
    from benchmark.db.repository import ResponseRepository

    q = cached_questionnaire("1.0.0")
    response = _full_response()
    val = ValidationEngine(q).validate(response)

    repo = ResponseRepository()
    _make_snapshot_record(db)
    repo.save_response(db, response, val)
    db.commit()

    answers = db.query(AnswerRecord).filter_by(session_id=response.response_id).all()
    assert len(answers) == len(response.answers)

    # Verificar que no hay campos de texto libre que puedan identificar
    for ans in answers:
        assert ans.question_id  # solo IDs estructurados
        assert ans.option_id
        # No hay columna de texto libre, nombre, email ni empresa


def test_contact_store_separate_from_analytics(db):
    """El email del contacto NO está en la misma tabla que las respuestas."""
    _make_snapshot_record(db)
    repo = ContactRepository()
    response_id = str(uuid.uuid4())

    repo.save_contact(db, response_id, "operador@example.com")
    db.commit()

    # ContactStore existe
    contacts = db.query(ContactStore).all()
    assert len(contacts) == 1

    # ContactStore NO tiene FK hacia response_sessions
    contact = contacts[0]
    assert hasattr(contact, "response_id_hash")
    assert not hasattr(contact, "session_id")  # no hay FK directa

    # El hash no permite reconstruir el response_id original
    stored_hash = contact.response_id_hash
    assert stored_hash != response_id
    assert stored_hash == hashlib.sha256(response_id.encode()).hexdigest()


def test_idempotency_same_key_returns_same_response(db):
    """Enviar la misma idempotency_key dos veces produce el mismo response_id."""
    from benchmark.engines.validation import ValidationEngine
    from benchmark.db.repository import ResponseRepository

    q = cached_questionnaire("1.0.0")
    idem_key = "idem-test-001"

    response = _full_response()
    response.idempotency_key = idem_key
    val = ValidationEngine(q).validate(response)

    repo = ResponseRepository()
    _make_snapshot_record(db)
    repo.save_response(db, response, val)
    db.commit()

    found = repo.find_by_idempotency_key(db, idem_key)
    assert found is not None
    assert found.id == response.response_id


def test_contact_purge_expired(db):
    """Los registros de contacto expirados se marcan como eliminados."""
    _make_snapshot_record(db)
    repo = ContactRepository()

    # Guardar contacto ya expirado (expires_at en el pasado)
    expired = ContactStore(
        response_id_hash="abc123",
        encrypted_email="test@test.com",
        expires_at=datetime.utcnow() - timedelta(days=1),
    )
    db.add(expired)
    db.commit()

    n = repo.purge_expired(db)
    db.commit()

    assert n == 1
    record = db.query(ContactStore).first()
    assert record.deleted_at is not None


def test_snapshot_publish_atomic(db):
    """Publicar un snapshot nuevo marca el anterior como superseded."""
    repo = SnapshotRepository()

    snap1 = BenchmarkSnapshotRecord(
        id="snap-v1", status=SnapshotStatus.PUBLISHED.value,
        questionnaire_version="1.0.0", scoring_version="1.0.0",
        cohort_version="1.0.0", rebalancing_version="1.0.0",
        published_at=datetime.utcnow(),
        distributions_json={}, top_quartile_practices_json=[],
        rebalancing_weights_json={}, privacy_thresholds_json={},
    )
    snap2 = BenchmarkSnapshotRecord(
        id="snap-v2", status=SnapshotStatus.DRAFT.value,
        questionnaire_version="1.0.0", scoring_version="1.0.0",
        cohort_version="1.0.0", rebalancing_version="1.0.0",
        distributions_json={}, top_quartile_practices_json=[],
        rebalancing_weights_json={}, privacy_thresholds_json={},
    )
    db.add_all([snap1, snap2])
    db.commit()

    repo.publish_snapshot(db, "snap-v2", approved_by="test_user")
    db.commit()

    old = db.get(BenchmarkSnapshotRecord, "snap-v1")
    new = db.get(BenchmarkSnapshotRecord, "snap-v2")
    assert old.status == SnapshotStatus.SUPERSEDED.value
    assert new.status == SnapshotStatus.PUBLISHED.value
    assert new.approved_by == "test_user"


def test_audit_events_logged(db):
    """Los eventos de auditoría se registran sin respuestas completas."""
    _make_snapshot_record(db)
    audit = AuditRepository()

    audit.log(db, "response.received", "response_session", "r-001",
               metadata={"status": "valid"})
    audit.log(db, "result.generated", "operator_result", "res-001",
               metadata={"snapshot_id": "snap-001"})
    db.commit()

    events = db.query(AuditEventRecord).all()
    assert len(events) == 2
    assert events[0].event_type == "response.received"

    # Los metadatos no contienen respuestas completas
    for ev in events:
        assert "answers" not in ev.metadata_json
        assert "email" not in ev.metadata_json


def test_result_persisted_before_response(db):
    """El resultado se puede recuperar después de guardarlo."""
    from tests.test_integration import _make_snapshot, _full_response_from_yaml
    from benchmark.db.repository import SnapshotRepository

    snap = _make_snapshot()

    # Registrar el snapshot en la DB para satisfacer la FK de operator_results
    snap_repo = SnapshotRepository()
    snap_repo.save_snapshot(db, snap)
    db.flush()
    # Publicarlo directamente
    snap_record = db.get(BenchmarkSnapshotRecord, snap.snapshot_id)
    snap_record.status = "published"
    snap_record.published_at = datetime.utcnow()
    db.flush()

    use_case = ProcessResponseUseCase(
        snapshot=snap,
        result_id_factory=lambda: str(uuid.uuid4()),
        methodology_version="1.0.0",
    )
    response = _full_response_from_yaml(score_level="mid")

    result = use_case.execute(response, db=db)
    db.commit()

    assert result.success
    record = db.query(OperatorResultRecord).filter_by(
        session_id=response.response_id
    ).first()
    assert record is not None
    assert record.questionnaire_version == "1.0.0"


def test_coarse_cohort_attributes_only(db):
    """Solo se persisten bandas de cohorte, nunca valores exactos."""
    from benchmark.engines.validation import ValidationEngine
    from benchmark.db.repository import ResponseRepository

    q = cached_questionnaire("1.0.0")
    response = _full_response()
    # Simular que el operador pasó una banda ya normalizada
    response.cohort_attributes.capacity_band = "large"  # banda, no "42.5 MW"
    val = ValidationEngine(q).validate(response)

    _make_snapshot_record(db)
    ResponseRepository().save_response(db, response, val)
    db.commit()

    record = db.get(ResponseSessionRecord, response.response_id)
    # Solo hay columnas de banda — no hay capacidad exacta
    assert record.capacity_band == "large"
    assert not hasattr(record, "capacity_exact_mw")
