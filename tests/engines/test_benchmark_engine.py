"""
Tests PR 8 — Motor de benchmark y percentiles (backlog §3.4).
"""
from __future__ import annotations

import pytest

from app.engines.benchmark_engine import BenchmarkEngine


@pytest.fixture
def engine():
    return BenchmarkEngine()


def _dist_uniforme(n=100) -> list[float]:
    """Distribución uniforme de 0 a 100."""
    return [i * 100 / (n - 1) for i in range(n)]


# ── Percentiles en rango ──────────────────────────────────────────────────────

def test_percentil_en_rango_0_100(engine):
    dist = _dist_uniforme()
    result = engine.calcular(
        scores_operador={"latencia": 50.0},
        distribuciones={"latencia": dist},
        grupo_comparable="global",
    )
    pd = result.get("latencia")
    assert 0.0 <= pd.percentil <= 100.0


def test_score_maximo_percentil_alto(engine):
    """Score 100 en distribución uniforme → percentil cerca de 100."""
    dist = _dist_uniforme(100)
    result = engine.calcular({"latencia": 100.0}, {"latencia": dist}, "global")
    assert result.get("latencia").percentil >= 95.0


def test_score_minimo_percentil_bajo(engine):
    """Score 0 en distribución uniforme → percentil = 0."""
    dist = _dist_uniforme(100)
    result = engine.calcular({"latencia": 0.0}, {"latencia": dist}, "global")
    assert result.get("latencia").percentil == 0.0


def test_score_mediana_percentil_cerca_50(engine):
    """Score igual a la mediana → percentil ≈ 50%."""
    dist = [float(i) for i in range(0, 101)]   # 0-100
    result = engine.calcular({"latencia": 50.0}, {"latencia": dist}, "global")
    pd = result.get("latencia")
    assert 45.0 <= pd.percentil <= 55.0


# ── Estadísticas robustas (doc §3.4: mediana y cuartiles, no promedio) ────────

def test_mediana_correcta(engine):
    dist = [10.0, 20.0, 30.0, 40.0, 50.0]
    result = engine.calcular({"latencia": 30.0}, {"latencia": dist}, "global")
    assert result.get("latencia").mediana_ref == pytest.approx(30.0, abs=0.1)


def test_p75_es_umbral_top_25_pct(engine):
    """p75 es el mínimo score para estar en el cuartil superior."""
    dist = [float(i) for i in range(0, 101)]
    result = engine.calcular({"latencia": 75.0}, {"latencia": dist}, "global")
    pd = result.get("latencia")
    assert pd.p75_ref == pytest.approx(75.0, abs=1.0)


def test_p25_menor_que_mediana_menor_que_p75(engine):
    dist = [float(i) for i in range(0, 101)]
    result = engine.calcular({"latencia": 50.0}, {"latencia": dist}, "global")
    pd = result.get("latencia")
    assert pd.p25_ref < pd.mediana_ref < pd.p75_ref


# ── Sin distribución de referencia ────────────────────────────────────────────

def test_sin_distribucion_percentil_neutral(engine):
    """Sin datos de referencia → percentil = 50 (neutral), sin error."""
    result = engine.calcular(
        scores_operador={"latencia": 75.0},
        distribuciones={},
        grupo_comparable="global",
    )
    pd = result.get("latencia")
    assert pd.percentil == 50.0
    assert pd.n_referencia == 0


# ── Varias dimensiones ────────────────────────────────────────────────────────

def test_cinco_dimensiones_calculadas(engine):
    dims = ["latencia", "visibilidad", "atribucion_friccion",
            "auto_cuantificacion", "bloqueantes"]
    scores = {d: 50.0 for d in dims}
    dists = {d: _dist_uniforme() for d in dims}
    result = engine.calcular(scores, dists, "global")
    assert len(result.dimensiones) == 5
    for dim in dims:
        assert result.get(dim) is not None


def test_grupo_comparable_registrado(engine):
    result = engine.calcular({"latencia": 50.0}, {"latencia": _dist_uniforme()}, "latam_colo")
    assert result.grupo_comparable == "latam_colo"
    assert result.get("latencia").grupo_comparable == "latam_colo"


# ── Determinismo ──────────────────────────────────────────────────────────────

def test_mismo_input_mismo_percentil(engine):
    dist = _dist_uniforme(200)
    r1 = engine.calcular({"latencia": 67.0}, {"latencia": dist}, "global")
    r2 = engine.calcular({"latencia": 67.0}, {"latencia": dist}, "global")
    assert r1.get("latencia").percentil == r2.get("latencia").percentil
