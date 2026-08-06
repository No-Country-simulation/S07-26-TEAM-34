"""Tests PR 9 — Motor top quartile (backlog §3.5)."""
from __future__ import annotations
import pytest
from app.engines.top_quartile_engine import TopQuartileEngine

DIMS = ["latencia", "visibilidad", "atribucion_friccion", "auto_cuantificacion", "bloqueantes"]

@pytest.fixture
def engine():
    return TopQuartileEngine()

def test_brecha_cuando_por_debajo_del_top(engine):
    result = engine.analizar(
        scores_operador={"latencia": 40.0},
        percentiles_operador={"latencia": 40.0},
        umbrales_p75={"latencia": 70.0},
    )
    assert len(result.brechas) == 1
    assert result.brechas[0].dimension == "latencia"

def test_sin_brecha_cuando_en_top(engine):
    result = engine.analizar(
        scores_operador={"latencia": 85.0},
        percentiles_operador={"latencia": 80.0},
        umbrales_p75={"latencia": 70.0},
    )
    assert result.brechas == []
    assert "latencia" in result.dimensiones_en_top

def test_descripcion_especifica_no_generica(engine):
    result = engine.analizar(
        scores_operador={"visibilidad": 30.0},
        percentiles_operador={"visibilidad": 30.0},
        umbrales_p75={"visibilidad": 65.0},
    )
    desc = result.brechas[0].descripcion
    assert "30" in desc
    assert "65" in desc

def test_cinco_dimensiones(engine):
    scores = {d: 40.0 for d in DIMS}
    pcts = {d: 40.0 for d in DIMS}
    p75s = {d: 70.0 for d in DIMS}
    result = engine.analizar(scores, pcts, p75s)
    assert len(result.brechas) == 5
    assert result.dimensiones_en_top == []

def test_mezcla_top_y_brechas(engine):
    scores = {"latencia": 40.0, "visibilidad": 90.0}
    pcts = {"latencia": 35.0, "visibilidad": 85.0}
    p75s = {"latencia": 70.0, "visibilidad": 70.0}
    result = engine.analizar(scores, pcts, p75s)
    assert len(result.brechas) == 1
    assert "visibilidad" in result.dimensiones_en_top
