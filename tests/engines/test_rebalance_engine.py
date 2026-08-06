"""
Tests PR 7 — Motor de rebalanceo (backlog §3.3, doc §9).

Verifica la fórmula exacta:
    peso_primario = (n_valido / (n_valido + k)) × factor_diversidad
    peso_publico  = 1 - peso_primario
"""
from __future__ import annotations

import pytest

from app.engines.rebalance_engine import RebalanceEngine, K


@pytest.fixture
def engine():
    return RebalanceEngine(k=K)


# ── Casos borde documentados (doc §9) ─────────────────────────────────────────

def test_sin_datos_primarios_peso_primario_cero(engine):
    """n_valido = 0 → peso_primario = 0, peso_publico = 1."""
    result = engine.rebalancear(
        scores_publicos=[50.0] * 100,
        scores_primarios=[],
        categorias_cubiertas=0,
    )
    assert result.peso_primario == 0.0
    assert result.peso_publico == 1.0
    assert result.n_valido == 0


def test_factor_diversidad_cero_frena_peso(engine):
    """Factor diversidad = 0 → peso_primario = 0, aunque haya datos."""
    result = engine.rebalancear(
        scores_publicos=[50.0] * 100,
        scores_primarios=[60.0] * 30,
        categorias_cubiertas=0,   # sin diversidad
    )
    assert result.peso_primario == 0.0
    assert result.factor_diversidad == 0.0


def test_pesos_suman_uno(engine):
    """peso_publico + peso_primario == 1 siempre."""
    for n in [0, 1, 10, 50, 200]:
        result = engine.rebalancear(
            scores_publicos=[50.0] * 100,
            scores_primarios=[60.0] * n,
            categorias_cubiertas=20,
        )
        assert abs(result.peso_publico + result.peso_primario - 1.0) < 1e-5


# ── Fórmula con k=50 (doc §9 — valores de referencia) ────────────────────────

def test_n50_k50_diversidad_maxima_peso_primario_aprox_50pct(engine):
    """Con n=50, k=50, diversidad=1.0 → peso_primario ≈ 50%."""
    total_cats = engine._cfg.segmentacion.total_categorias()
    result = engine.rebalancear(
        scores_publicos=[50.0] * 200,
        scores_primarios=[60.0] * 50,
        categorias_cubiertas=total_cats,  # diversidad = 1.0
    )
    assert result.peso_primario == pytest.approx(50 / (50 + 50), abs=0.01)


def test_n200_k50_diversidad_maxima_peso_primario_aprox_80pct(engine):
    """Con n=200, k=50, diversidad=1.0 → peso_primario ≈ 80%."""
    total_cats = engine._cfg.segmentacion.total_categorias()
    result = engine.rebalancear(
        scores_publicos=[50.0] * 200,
        scores_primarios=[60.0] * 200,
        categorias_cubiertas=total_cats,
    )
    assert result.peso_primario == pytest.approx(200 / (200 + 50), abs=0.01)


def test_diversidad_parcial_frena_crecimiento(engine):
    """Con diversidad baja el peso primario crece más lento que con diversidad alta."""
    total_cats = engine._cfg.segmentacion.total_categorias()
    alta = engine.rebalancear([50.0]*200, [60.0]*50, categorias_cubiertas=total_cats)
    baja = engine.rebalancear([50.0]*200, [60.0]*50, categorias_cubiertas=1)
    assert alta.peso_primario > baja.peso_primario


def test_mas_datos_mas_peso_primario(engine):
    """Más n_valido → más peso primario (función monotónica creciente)."""
    total_cats = engine._cfg.segmentacion.total_categorias()
    r10  = engine.rebalancear([50.0]*200, [60.0]*10,  total_cats)
    r50  = engine.rebalancear([50.0]*200, [60.0]*50,  total_cats)
    r200 = engine.rebalancear([50.0]*200, [60.0]*200, total_cats)
    assert r10.peso_primario < r50.peso_primario < r200.peso_primario


def test_peso_primario_entre_0_y_1(engine):
    """peso_primario siempre en [0, 1]."""
    total_cats = engine._cfg.segmentacion.total_categorias()
    for n in [0, 1, 5, 50, 500]:
        result = engine.rebalancear([50.0]*200, [60.0]*n, total_cats)
        assert 0.0 <= result.peso_primario <= 1.0


# ── Distribución combinada ────────────────────────────────────────────────────

def test_distribucion_combinada_no_vacia_con_datos(engine):
    result = engine.rebalancear(
        scores_publicos=[40.0, 50.0, 60.0],
        scores_primarios=[70.0, 80.0],
        categorias_cubiertas=5,
    )
    assert len(result.distribucion_combinada) > 0


def test_distribucion_combinada_vacia_sin_datos(engine):
    result = engine.rebalancear(
        scores_publicos=[],
        scores_primarios=[],
        categorias_cubiertas=0,
    )
    assert result.distribucion_combinada == []


def test_sin_primarios_distribucion_es_solo_publica(engine):
    """Sin datos primarios la distribución viene 100% del público."""
    publicos = [10.0, 20.0, 30.0, 40.0, 50.0]
    result = engine.rebalancear(
        scores_publicos=publicos,
        scores_primarios=[],
        categorias_cubiertas=0,
    )
    assert result.peso_primario == 0.0
    assert len(result.distribucion_combinada) > 0


# ── Nota de baja diversidad ───────────────────────────────────────────────────

def test_nota_baja_diversidad_aparece(engine):
    result = engine.rebalancear([50.0]*100, [60.0]*30, categorias_cubiertas=1)
    assert any("iversidad" in n for n in result.notas)


def test_nota_sin_datos_primarios_aparece(engine):
    result = engine.rebalancear([50.0]*100, [], 0)
    assert any("100%" in n or "público" in n for n in result.notas)


# ── Determinismo ──────────────────────────────────────────────────────────────

def test_pesos_son_deterministas(engine):
    """Los pesos (no la distribución) son siempre iguales con el mismo input."""
    total_cats = engine._cfg.segmentacion.total_categorias()
    r1 = engine.rebalancear([50.0]*100, [60.0]*30, total_cats)
    r2 = engine.rebalancear([50.0]*100, [60.0]*30, total_cats)
    assert r1.peso_primario == r2.peso_primario
    assert r1.factor_diversidad == r2.factor_diversidad
