"""
Tests para el seed del dataset público sintético (PR 1 — Guia_PRs_Migracion.md).

Verifica que:
- Las 3 tablas se crean sin error
- Insertar una fila válida en cada tabla funciona
- Los campos enum rechazan valores fuera de la lista permitida
- La integridad referencial se mantiene
- El script de seed carga las 1.000 filas correctamente
"""
from __future__ import annotations

import pytest
from sqlalchemy import inspect

from app.models.database import Base, get_engine, get_session
from app.models.tables import DimensionEnum, DimensionScore, Operator, Result, SourceEnum


# ── Tests de creación de tablas ───────────────────────────────────────────────

def test_las_tres_tablas_se_crean_sin_error():
    """Verifica que las 3 tablas del esquema se crean correctamente."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    
    inspector = inspect(engine)
    tablas = inspector.get_table_names()
    
    assert "operators" in tablas
    assert "dimension_scores" in tablas
    assert "results" in tablas


# ── Tests de inserción válida ───────────────────────────────────────────────────

def test_insertar_fila_valida_en_operators():
    """Insertar una fila válida en operators funciona."""
    import uuid
    test_id = str(uuid.uuid4())
    
    with get_session() as session:
        op = Operator(
            id=test_id,
            source=SourceEnum.public_synthetic,
            region="latam",
            facility_size="menos_1mw",
            dc_type="enterprise",
            benchmark_version="1.0.0",
            dimension_version="1.0.0",
        )
        session.add(op)
        session.commit()
        
        # Verificar que se guardó
        recuperado = session.get(Operator, test_id)
        assert recuperado is not None
        assert recuperado.source == SourceEnum.public_synthetic
        assert recuperado.region == "latam"
        
        # Cleanup
        session.delete(recuperado)
        session.commit()


def test_insertar_fila_valida_en_dimension_scores():
    """Insertar una fila válida en dimension_scores funciona."""
    import uuid
    test_id = str(uuid.uuid4())
    
    with get_session() as session:
        # Primero crear el operator
        op = Operator(
            id=test_id,
            source=SourceEnum.primary,
            region="norteamerica",
            facility_size="mas_20mw",
            dc_type="hyperscale",
            benchmark_version="1.0.0",
            dimension_version="1.0.0",
        )
        session.add(op)
        session.commit()
        
        # Luego crear dimension_score
        ds = DimensionScore(
            operator_id=test_id,
            dimension=DimensionEnum.latencia,
            score=75.5,
            raw_answers={"p1_minutos": 10, "p2_minutos": 15, "p3": "automatizado"},
        )
        session.add(ds)
        session.commit()
        
        # Verificar que se guardó
        recuperado = session.query(DimensionScore).filter_by(
            operator_id=test_id,
            dimension=DimensionEnum.latencia
        ).first()
        assert recuperado is not None
        assert recuperado.score == 75.5
        
        # Cleanup
        session.delete(recuperado)
        session.delete(op)
        session.commit()


def test_insertar_fila_valida_en_results():
    """Insertar una fila válida en results funciona."""
    import uuid
    test_id = str(uuid.uuid4())
    
    with get_session() as session:
        # Primero crear el operator
        op = Operator(
            id=test_id,
            source=SourceEnum.primary,
            region="europa",
            facility_size="5_20mw",
            dc_type="colocation",
            benchmark_version="1.0.0",
            dimension_version="1.0.0",
        )
        session.add(op)
        session.commit()
        
        # Luego crear result
        result = Result(
            operator_id=test_id,
            percentiles={"latencia": 50.0, "visibilidad": 75.0},
            friccion_principal="latencia",
            profile="operacion_optimizada",
            top_quartile_gaps={"latencia": "Gap descripción"},
            diagnostico_texto="Diagnóstico de prueba",
        )
        session.add(result)
        session.commit()
        
        # Verificar que se guardó
        recuperado = session.get(Result, test_id)
        assert recuperado is not None
        assert recuperado.profile == "operacion_optimizada"
        
        # Cleanup
        session.delete(recuperado)
        session.delete(op)
        session.commit()


# ── Tests de validación de enums ────────────────────────────────────────────────

def test_enum_source_rechaza_valor_fuera_de_lista():
    """El campo source en operators rechaza valores fuera de la lista permitida."""
    with get_session() as session:
        with pytest.raises(ValueError):  # El validador lanza ValueError
            op = Operator(
                id="test-operator-invalid",
                source="valor_invalido",  # No está en SourceEnum
                region="latam",
                facility_size="menos_1mw",
                dc_type="enterprise",
                benchmark_version="1.0.0",
                dimension_version="1.0.0",
            )
            session.add(op)
            session.commit()


def test_enum_dimension_rechaza_valor_fuera_de_lista():
    """El campo dimension en dimension_scores rechaza valores fuera de la lista permitida."""
    import uuid
    test_id = str(uuid.uuid4())
    
    with get_session() as session:
        # Primero crear el operator
        op = Operator(
            id=test_id,
            source=SourceEnum.primary,
            region="apac",
            facility_size="1_5mw",
            dc_type="edge",
            benchmark_version="1.0.0",
            dimension_version="1.0.0",
        )
        session.add(op)
        session.commit()
        
        # Intentar crear dimension_score con dimension inválida
        with pytest.raises(ValueError):
            ds = DimensionScore(
                operator_id=test_id,
                dimension="dimension_invalida",  # No está en DimensionEnum
                score=50.0,
                raw_answers={},
            )
            session.add(ds)
            session.commit()
        
        # Cleanup
        session.delete(op)
        session.commit()


# ── Tests de integridad referencial ─────────────────────────────────────────────

def test_insertar_dimension_score_sin_operator_falla():
    """Insertar en dimension_scores con operator_id que no existe falla."""
    with get_session() as session:
        ds = DimensionScore(
            operator_id="operator-inexistente-ds",
            dimension=DimensionEnum.visibilidad,
            score=60.0,
            raw_answers={},
        )
        session.add(ds)
        
        with pytest.raises(Exception):  # FK violation (SQLite IntegrityError o SQLAlchemy error)
            session.commit()
        
        session.rollback()  # Limpiar para tests siguientes


def test_insertar_result_sin_operator_falla():
    """Insertar en results con operator_id que no existe falla."""
    with get_session() as session:
        result = Result(
            operator_id="operator-inexistente-result",
            percentiles={},
            friccion_principal="",
            profile="",
            top_quartile_gaps={},
            diagnostico_texto="",
        )
        session.add(result)
        
        with pytest.raises(Exception):  # FK violation
            session.commit()
        
        session.rollback()  # Limpiar para tests siguientes


# ── Tests del script de seed ────────────────────────────────────────────────────

def test_seed_carga_1000_filas_correctamente():
    """
    El script de seed carga las 1.000 filas del CSV correctamente.
    Contar filas en operators con source="public_synthetic" después de correrlo.
    Nota: El test verifica que hay al menos 1000 (puede haber más por tests de integración).
    """
    with get_session() as session:
        count = session.query(Operator).filter_by(source=SourceEnum.public_synthetic).count()
        assert count >= 1000, f"Se esperaban al menos 1000 registros públicos, se encontraron {count}"


def test_seed_carga_5_dimension_scores_por_operator():
    """Cada operator público debe tener exactamente 5 dimension_scores."""
    with get_session() as session:
        # Tomar una muestra de operators públicos
        operators = session.query(Operator).filter_by(source=SourceEnum.public_synthetic).limit(10).all()
        
        for op in operators:
            scores = session.query(DimensionScore).filter_by(operator_id=op.id).all()
            assert len(scores) == 5, f"Operator {op.id} tiene {len(scores)} dimension_scores, se esperaban 5"


def test_dataset_publico_tiene_valores_validos():
    """Verificar que los scores del dataset público están en rango válido (0-100)."""
    with get_session() as session:
        scores = session.query(DimensionScore.score)\
            .join(Operator, Operator.id == DimensionScore.operator_id)\
            .filter(Operator.source == SourceEnum.public_synthetic)\
            .all()
        
        for (score,) in scores:
            assert 0 <= score <= 100, f"Score inválido: {score}"


def test_dataset_publico_cubre_todas_las_dimensiones():
    """Verificar que el dataset público tiene datos para todas las dimensiones."""
    with get_session() as session:
        for dimension in DimensionEnum:
            count = session.query(DimensionScore)\
                .join(Operator, Operator.id == DimensionScore.operator_id)\
                .filter(
                    Operator.source == SourceEnum.public_synthetic,
                    DimensionScore.dimension == dimension
                )\
                .count()
            
            assert count == 1000, f"Dimensión {dimension} tiene {count} registros, se esperaban 1000"
