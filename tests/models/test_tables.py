"""
Tests PR 1 — Modelo de datos (backlog sección 11).

Cubre:
- Las 3 tablas se crean sin error
- Insertar una fila válida en cada tabla funciona
- Los enums rechazan valores fuera de la lista permitida
- FK: insertar en dimension_scores con operator_id inexistente falla
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker, Session

from app.models.database import Base
from app.models.tables import DimensionEnum, DimensionScore, Operator, Result, SourceEnum


# ── Fixture: DB SQLite en memoria ─────────────────────────────────────────────

@pytest.fixture(scope="function")
def db() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def fk_pragma(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    SL = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SL()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def _new_operator(**kwargs) -> Operator:
    defaults = dict(
        id=str(uuid.uuid4()),
        source=SourceEnum.primary,
        region="latam",
        facility_size="1-5 MW",
        dc_type="colo",
        benchmark_version="1.0.0",
        dimension_version="1.0.0",
    )
    defaults.update(kwargs)
    return Operator(**defaults)


# ── Las 3 tablas se crean ─────────────────────────────────────────────────────

def test_tables_created(db):
    """Las 3 tablas existen y se pueden consultar."""
    assert db.query(Operator).count() == 0
    assert db.query(DimensionScore).count() == 0
    assert db.query(Result).count() == 0


# ── operators ─────────────────────────────────────────────────────────────────

def test_insert_operator_valid(db):
    op = _new_operator()
    db.add(op)
    db.commit()
    found = db.get(Operator, op.id)
    assert found is not None
    assert found.source == SourceEnum.primary
    assert found.region == "latam"


def test_operator_source_public_synthetic(db):
    op = _new_operator(source=SourceEnum.public_synthetic)
    db.add(op)
    db.commit()
    assert db.get(Operator, op.id).source == SourceEnum.public_synthetic


def test_operator_nullable_context_fields(db):
    """region, facility_size y dc_type son opcionales."""
    op = _new_operator(region=None, facility_size=None, dc_type=None)
    db.add(op)
    db.commit()
    found = db.get(Operator, op.id)
    assert found.region is None
    assert found.facility_size is None


def test_operator_created_at_has_value(db):
    op = _new_operator()
    db.add(op)
    db.commit()
    assert db.get(Operator, op.id).created_at is not None


def test_operator_source_rejects_invalid_value(db):
    """Un valor de source fuera del enum falla."""
    with pytest.raises(Exception):
        op = Operator(
            id=str(uuid.uuid4()),
            source="invalid_source",   # fuera del enum
            benchmark_version="1.0.0",
            dimension_version="1.0.0",
        )
        db.add(op)
        db.commit()


# ── dimension_scores ──────────────────────────────────────────────────────────

def test_insert_dimension_score_valid(db):
    op = _new_operator()
    db.add(op)
    db.flush()

    score = DimensionScore(
        operator_id=op.id,
        dimension=DimensionEnum.latencia,
        score=75.0,
        raw_answers={"p1_minutos": 8, "p2_minutos": 15, "p3": "alertas_manuales"},
    )
    db.add(score)
    db.commit()

    found = db.query(DimensionScore).filter_by(operator_id=op.id).first()
    assert found is not None
    assert found.score == 75.0
    assert found.raw_answers["p1_minutos"] == 8


def test_insert_all_five_dimensions(db):
    op = _new_operator()
    db.add(op)
    db.flush()

    for dim in DimensionEnum:
        db.add(DimensionScore(
            operator_id=op.id,
            dimension=dim,
            score=50.0,
            raw_answers={},
        ))
    db.commit()

    assert db.query(DimensionScore).filter_by(operator_id=op.id).count() == 5


def test_dimension_score_unique_per_operator_dimension(db):
    """No puede haber dos scores del mismo operador para la misma dimensión."""
    op = _new_operator()
    db.add(op)
    db.flush()

    db.add(DimensionScore(operator_id=op.id, dimension=DimensionEnum.latencia,
                          score=50.0, raw_answers={}))
    db.commit()

    db.add(DimensionScore(operator_id=op.id, dimension=DimensionEnum.latencia,
                          score=80.0, raw_answers={}))
    with pytest.raises(IntegrityError):
        db.commit()


def test_dimension_enum_rejects_invalid_value(db):
    """Dimension fuera del enum falla."""
    op = _new_operator()
    db.add(op)
    db.flush()

    with pytest.raises(Exception):
        db.add(DimensionScore(
            operator_id=op.id,
            dimension="dimension_inexistente",
            score=50.0,
            raw_answers={},
        ))
        db.commit()


def test_fk_dimension_score_rejects_missing_operator(db):
    """Insertar un score con operator_id que no existe falla por FK."""
    db.add(DimensionScore(
        operator_id=str(uuid.uuid4()),  # no existe en operators
        dimension=DimensionEnum.visibilidad,
        score=40.0,
        raw_answers={},
    ))
    with pytest.raises(IntegrityError):
        db.commit()


def test_dimension_score_range(db):
    """Score debe estar entre 0 y 100 — insertamos los límites."""
    op = _new_operator()
    db.add(op)
    db.flush()

    db.add(DimensionScore(operator_id=op.id, dimension=DimensionEnum.visibilidad,
                          score=0.0, raw_answers={}))
    db.add(DimensionScore(operator_id=op.id, dimension=DimensionEnum.bloqueantes,
                          score=100.0, raw_answers={}))
    db.commit()

    scores = db.query(DimensionScore).filter_by(operator_id=op.id).all()
    values = {s.dimension: s.score for s in scores}
    assert values[DimensionEnum.visibilidad] == 0.0
    assert values[DimensionEnum.bloqueantes] == 100.0


# ── results ───────────────────────────────────────────────────────────────────

def test_insert_result_valid(db):
    op = _new_operator()
    db.add(op)
    db.flush()

    result = Result(
        operator_id=op.id,
        percentiles={"latencia": 45.0, "visibilidad": 60.0},
        friccion_principal="latencia",
        profile="operacion_reactiva",
        top_quartile_gaps={"latencia": "El top 25% tiene ajuste automatizado"},
        diagnostico_texto="Tu principal área de mejora es la latencia de coordinación.",
    )
    db.add(result)
    db.commit()

    found = db.get(Result, op.id)
    assert found is not None
    assert found.friccion_principal == "latencia"
    assert found.percentiles["latencia"] == 45.0


def test_result_fk_rejects_missing_operator(db):
    """Result sin operator válido falla por FK."""
    db.add(Result(
        operator_id=str(uuid.uuid4()),
        percentiles={},
        friccion_principal="latencia",
        profile="reactivo",
        top_quartile_gaps={},
        diagnostico_texto="",
    ))
    with pytest.raises(IntegrityError):
        db.commit()


def test_result_computed_at_auto(db):
    op = _new_operator()
    db.add(op)
    db.flush()

    result = Result(
        operator_id=op.id,
        percentiles={},
        friccion_principal="visibilidad",
        profile="parcial",
        top_quartile_gaps={},
        diagnostico_texto="",
    )
    db.add(result)
    db.commit()

    assert db.get(Result, op.id).computed_at is not None


# ── Relaciones entre tablas ───────────────────────────────────────────────────

def test_cascade_delete_scores_with_operator(db):
    """Al borrar un operator, sus scores se eliminan en cascada."""
    op = _new_operator()
    db.add(op)
    db.flush()
    db.add(DimensionScore(operator_id=op.id, dimension=DimensionEnum.latencia,
                          score=50.0, raw_answers={}))
    db.commit()

    db.delete(op)
    db.commit()

    assert db.query(DimensionScore).filter_by(operator_id=op.id).count() == 0


def test_cascade_delete_result_with_operator(db):
    """Al borrar un operator, su result se elimina en cascada."""
    op = _new_operator()
    db.add(op)
    db.flush()
    db.add(Result(operator_id=op.id, percentiles={}, friccion_principal="latencia",
                  profile="p", top_quartile_gaps={}, diagnostico_texto=""))
    db.commit()

    db.delete(op)
    db.commit()

    assert db.get(Result, op.id) is None
