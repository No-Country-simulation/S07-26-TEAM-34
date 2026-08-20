"""Tests PR 9 — Motor de interpretación (backlog §3.6)."""
from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from app.engines.interpretation_engine import InterpretationEngine
from app.engines.benchmark_engine import BenchmarkEngine, BenchmarkResult
from app.engines.top_quartile_engine import TopQuartileEngine, TopQuartileResult


def _benchmark(scores: dict) -> BenchmarkResult:
    dist = [float(i) for i in range(0, 101)]
    return BenchmarkEngine().calcular(
        scores_operador=scores,
        distribuciones={d: dist for d in scores},
        grupo_comparable="global",
    )

def _top(scores: dict, pcts: dict) -> TopQuartileResult:
    return TopQuartileEngine().analizar(
        scores_operador=scores,
        percentiles_operador=pcts,
        umbrales_p75={d: 75.0 for d in scores},
    )

SCORES_BAJO = {d: 30.0 for d in
    ["latencia","visibilidad","atribucion_friccion","auto_cuantificacion","bloqueantes"]}
SCORES_ALTO = {d: 85.0 for d in
    ["latencia","visibilidad","atribucion_friccion","auto_cuantificacion","bloqueantes"]}


# ── Perfil determinístico ─────────────────────────────────────────────────────

def test_perfil_reactivo_latencia_y_visibilidad_bajos():
    engine = InterpretationEngine()
    scores = dict(SCORES_BAJO)
    scores["latencia"] = 30.0
    scores["visibilidad"] = 30.0
    result = engine.interpretar(scores, _benchmark(scores), _top(scores, {d: 30.0 for d in scores}))
    assert result.perfil == "operacion_reactiva"

def test_perfil_optimizado_scores_altos():
    engine = InterpretationEngine()
    result = engine.interpretar(SCORES_ALTO, _benchmark(SCORES_ALTO),
                                _top(SCORES_ALTO, {d: 85.0 for d in SCORES_ALTO}))
    assert result.perfil == "operacion_optimizada"

def test_perfil_visibilidad_limitada():
    engine = InterpretationEngine()
    scores = {d: 80.0 for d in SCORES_BAJO}
    scores["visibilidad"] = 30.0
    scores["latencia"] = 80.0
    result = engine.interpretar(scores, _benchmark(scores), _top(scores, {d: 50.0 for d in scores}))
    assert result.perfil == "visibilidad_limitada"


# ── Fricción principal ────────────────────────────────────────────────────────

def test_friccion_es_dimension_con_percentil_mas_bajo():
    engine = InterpretationEngine()
    scores = {"latencia": 20.0, "visibilidad": 80.0}
    bench = _benchmark(scores)
    result = engine.interpretar(scores, bench, _top(scores, {d: 30.0 for d in scores}))
    assert result.friccion_principal == "latencia"


# ── Fallback determinista ─────────────────────────────────────────────────────

def test_fallback_sin_llm_produce_texto():
    engine = InterpretationEngine(llm_client=None)
    result = engine.interpretar(SCORES_BAJO, _benchmark(SCORES_BAJO),
                                _top(SCORES_BAJO, {d: 30.0 for d in SCORES_BAJO}))
    assert not result.uso_llm
    assert len(result.diagnostico_texto) > 30

def test_fallback_texto_especifico_no_generico():
    engine = InterpretationEngine(llm_client=None)
    result = engine.interpretar(SCORES_BAJO, _benchmark(SCORES_BAJO),
                                _top(SCORES_BAJO, {d: 30.0 for d in SCORES_BAJO}))
    # Debe mencionar la dimensión con fricción — no texto genérico vacío
    assert any(kw in result.diagnostico_texto for kw in
               ["latencia","visibilidad","atribución","cuantificación","bloqueante"])


# ── LLM con fallback si falla ─────────────────────────────────────────────────

def test_llm_falla_usa_fallback():
    llm = MagicMock()
    llm.generar.side_effect = RuntimeError("LLM no disponible")
    engine = InterpretationEngine(llm_client=llm)
    result = engine.interpretar(SCORES_BAJO, _benchmark(SCORES_BAJO),
                                _top(SCORES_BAJO, {d: 30.0 for d in SCORES_BAJO}))
    assert not result.uso_llm
    assert len(result.diagnostico_texto) > 0

def test_llm_exitoso_usa_llm():
    llm = MagicMock()
    llm.generar.return_value = (
        '{"titular": "Fricción en bloqueantes", '
        '"razonamiento": "Diagnóstico generado por LLM con detalles específicos.", '
        '"accion_sugerida": "Revisar el detalle con el equipo responsable."}'
    )
    engine = InterpretationEngine(llm_client=llm)
    result = engine.interpretar(SCORES_BAJO, _benchmark(SCORES_BAJO),
                                _top(SCORES_BAJO, {d: 30.0 for d in SCORES_BAJO}))
    assert result.uso_llm
    assert "LLM" in result.diagnostico_texto
