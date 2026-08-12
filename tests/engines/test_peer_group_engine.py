"""Tests del motor de grupos comparables (backlog §3.2)."""
from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from app.engines.peer_group_engine import PeerGroupEngine, MIN_GROUP_SIZE


def _mock_session(counts: dict) -> MagicMock:
    """Session mock que devuelve counts según los filtros aplicados."""
    session = MagicMock()

    def scalar_side_effect(*args, **kwargs):
        # Devuelve el count según cuántos filtros se acumularon
        # Se detecta por el número de .filter() encadenados
        return counts.get("_default", 0)

    # Simular la cadena query().filter().filter()...scalar()
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.scalar.side_effect = lambda: counts.get("_default", 0)
    session.query.return_value = mock_query
    return session


@pytest.fixture
def engine():
    return PeerGroupEngine()


def test_nivel1_cuando_hay_suficientes_datos(engine):
    """Con suficientes datos en el grupo específico usa nivel 1."""
    session = MagicMock()
    mock_q = MagicMock()
    mock_q.filter.return_value = mock_q
    mock_q.scalar.return_value = MIN_GROUP_SIZE + 5
    session.query.return_value = mock_q

    result = engine.seleccionar("1-5MW", "LATAM", "colocation", session)
    assert result.nivel == 1
    assert "LATAM" in result.grupo_id
    assert "1-5MW" in result.grupo_id
    assert "colocation" in result.grupo_id


def test_fallback_a_global_sin_datos(engine):
    """Sin datos en ningún nivel específico cae a global."""
    session = MagicMock()
    mock_q = MagicMock()
    mock_q.filter.return_value = mock_q
    mock_q.scalar.return_value = 0
    session.query.return_value = mock_q

    result = engine.seleccionar("1-5MW", "LATAM", "colocation", session)
    assert result.nivel == 4
    assert result.grupo_id == "global"


def test_sin_contexto_cae_a_global(engine):
    """Sin contexto del operador siempre devuelve global."""
    session = MagicMock()
    mock_q = MagicMock()
    mock_q.filter.return_value = mock_q
    mock_q.scalar.return_value = 50
    session.query.return_value = mock_q

    result = engine.seleccionar(None, None, None, session)
    assert result.nivel == 4
    assert result.grupo_id == "global"


def test_descripcion_no_vacia(engine):
    session = MagicMock()
    mock_q = MagicMock()
    mock_q.filter.return_value = mock_q
    mock_q.scalar.return_value = 0
    session.query.return_value = mock_q

    result = engine.seleccionar("1-5MW", "Europe", "enterprise", session)
    assert result.descripcion


def test_n_registrado(engine):
    session = MagicMock()
    mock_q = MagicMock()
    mock_q.filter.return_value = mock_q
    mock_q.scalar.return_value = 25
    session.query.return_value = mock_q

    result = engine.seleccionar(">20MW", "North America", "hyperscale", session)
    assert result.n == 25
