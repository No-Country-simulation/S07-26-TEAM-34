"""
Tests PR 6 — Motor de scoring (backlog §3.1, doc metodológico §3-7).

Cubre: caso normal, casos borde documentados, casos inválidos,
fórmulas por dimensión, rangos de score 0-100.
"""
from __future__ import annotations

import pytest

from app.engines.scoring_engine import ScoringEngine
from app.schemas.request import CuestionarioRequest


def _req(**overrides) -> CuestionarioRequest:
    """Request base completo y válido."""
    data = {
        "contexto": {"facility_size": "1-5MW", "region": "Latinoamerica", "dc_type": "colocation"},
        "latencia": {"p1_minutos": 8.0, "p2_minutos": 20.0, "p3": "alertas_manual"},
        "visibilidad": {"p1_sistemas": 2, "p2": "diario", "p3": "un_rol"},
        "atribucion_friccion": {"p1": "energia_cooling", "p2": "estimacion", "p3": "revision_periodica"},
        "auto_cuantificacion": {
            "p1_capacidad_total": 10.0,
            "p2_capacidad_utilizable": 7.0,
            "unidad": "mw",
            "p3": "anual",
        },
        "bloqueantes": {"p1_bloqueantes": ["presupuesto"], "p2_severidad": "moderado"},
    }
    for key, val in overrides.items():
        data[key] = val
    return CuestionarioRequest(**data)


@pytest.fixture
def engine():
    return ScoringEngine()


# ── Scores en rango 0-100 ─────────────────────────────────────────────────────

def test_todos_los_scores_en_rango(engine):
    result = engine.score(_req())
    for sd in result.scores:
        assert 0.0 <= sd.score <= 100.0, f"{sd.dimension}: {sd.score} fuera de rango"


def test_cinco_dimensiones_presentes(engine):
    result = engine.score(_req())
    dims = {sd.dimension for sd in result.scores}
    assert dims == {
        "latencia", "visibilidad", "atribucion_friccion",
        "auto_cuantificacion", "bloqueantes"
    }


# ── Latencia — fórmula (score_p1 + score_p2 + score_p3) / 3 ─────────────────

def test_latencia_score_maximo(engine):
    """0 min + 0 min + automatizado → (100+100+100)/3 = 100"""
    req = _req(latencia={"p1_minutos": 0, "p2_minutos": 0, "p3": "automatizado"})
    sd = engine.score(req).get("latencia")
    assert sd.score == pytest.approx(100.0)


def test_latencia_score_minimo(engine):
    """1500 min + 1500 min + sin_proceso → (0+0+0)/3 = 0"""
    req = _req(latencia={"p1_minutos": 1500, "p2_minutos": 1500, "p3": "sin_proceso"})
    sd = engine.score(req).get("latencia")
    assert sd.score == pytest.approx(0.0)


def test_latencia_score_mixto(engine):
    """8 min (→75) + 20 min (→75) + alertas_manual (→67) → (75+75+67)/3 = 72.33"""
    req = _req(latencia={"p1_minutos": 8, "p2_minutos": 20, "p3": "alertas_manual"})
    sd = engine.score(req).get("latencia")
    assert sd.score == pytest.approx((75 + 75 + 67) / 3, abs=0.01)


def test_latencia_limite_bucket_5_vs_6(engine):
    """5 min → score 100; 6 min → score 75."""
    r5 = engine.score(_req(latencia={"p1_minutos": 5, "p2_minutos": 5, "p3": "automatizado"}))
    r6 = engine.score(_req(latencia={"p1_minutos": 6, "p2_minutos": 6, "p3": "automatizado"}))
    assert r5.get("latencia").desglose["p1"] == 100
    assert r6.get("latencia").desglose["p1"] == 75


def test_latencia_raw_answers_guardados(engine):
    req = _req(latencia={"p1_minutos": 8.5, "p2_minutos": 20.0, "p3": "alertas_manual"})
    sd = engine.score(req).get("latencia")
    assert sd.raw_answers["p1_minutos"] == 8.5
    assert sd.raw_answers["p3"] == "alertas_manual"


# ── Visibilidad — fórmula (score_p1 + score_p2 + score_p3) / 3 ───────────────

def test_visibilidad_score_maximo(engine):
    """1 sistema + tiempo_real + cualquiera → (100+100+100)/3 = 100"""
    req = _req(visibilidad={"p1_sistemas": 1, "p2": "tiempo_real", "p3": "cualquiera"})
    sd = engine.score(req).get("visibilidad")
    assert sd.score == pytest.approx(100.0)


def test_visibilidad_score_minimo(engine):
    req = _req(visibilidad={"p1_sistemas": 10, "p2": "nunca", "p3": "nadie"})
    sd = engine.score(req).get("visibilidad")
    assert sd.score == pytest.approx(0.0)


def test_visibilidad_2_sistemas_score_67(engine):
    req = _req(visibilidad={"p1_sistemas": 2, "p2": "diario", "p3": "un_rol"})
    sd = engine.score(req).get("visibilidad")
    assert sd.desglose["p1"] == 67
    assert sd.desglose["p2"] == 75
    assert sd.desglose["p3"] == 50


# ── Atribución — fórmula (score_p2 + score_p3) / 2, P1 nominal ───────────────

def test_atribucion_p1_no_entra_al_score(engine):
    """Cambiar P1 no debe cambiar el score."""
    r1 = engine.score(_req(atribucion_friccion={
        "p1": "energia_cooling", "p2": "con_medicion", "p3": "revision_activa"
    }))
    r2 = engine.score(_req(atribucion_friccion={
        "p1": "workload_energia", "p2": "con_medicion", "p3": "revision_activa"
    }))
    assert r1.get("atribucion_friccion").score == r2.get("atribucion_friccion").score


def test_atribucion_score_maximo(engine):
    """con_medicion (100) + revision_activa (100) → 100"""
    req = _req(atribucion_friccion={
        "p1": "energia_cooling", "p2": "con_medicion", "p3": "revision_activa"
    })
    sd = engine.score(req).get("atribucion_friccion")
    assert sd.score == pytest.approx(100.0)


def test_atribucion_caso_borde_no_sabria(engine):
    """P1='no_sabria_decir' → P2 y P3 se fuerzan a 0 → score = 0."""
    req = _req(atribucion_friccion={
        "p1": "no_sabria_decir", "p2": "con_medicion", "p3": "revision_activa"
    })
    sd = engine.score(req).get("atribucion_friccion")
    assert sd.score == pytest.approx(0.0)
    assert "no_sabria_decir" in sd.notas[0]


def test_atribucion_p1_guardado_en_raw(engine):
    req = _req(atribucion_friccion={
        "p1": "cooling_workload", "p2": "estimacion", "p3": "nunca_revisada"
    })
    sd = engine.score(req).get("atribucion_friccion")
    assert sd.raw_answers["p1"] == "cooling_workload"


# ── Auto-cuantificación — fórmula (completitud + score_p3) / 2 ───────────────

def test_auto_cuant_score_maximo(engine):
    """P1/P2 coherentes (→100) + continuamente (→100) → 100"""
    req = _req(auto_cuantificacion={
        "p1_capacidad_total": 10.0,
        "p2_capacidad_utilizable": 8.0,
        "unidad": "mw",
        "p3": "continuamente",
    })
    sd = engine.score(req).get("auto_cuantificacion")
    assert sd.score == pytest.approx(100.0)


def test_auto_cuant_sin_p1_p2_score_completitud_0(engine):
    req = _req(auto_cuantificacion={
        "p1_capacidad_total": None,
        "p2_capacidad_utilizable": None,
        "unidad": "mw",
        "p3": "anual",
    })
    sd = engine.score(req).get("auto_cuantificacion")
    assert sd.desglose["score_completitud_p1p2"] == 0
    assert sd.score == pytest.approx((0 + 33) / 2)


def test_auto_cuant_pct_varada_calculado(engine):
    """(10 - 7) / 10 * 100 = 30%"""
    req = _req(auto_cuantificacion={
        "p1_capacidad_total": 10.0,
        "p2_capacidad_utilizable": 7.0,
        "unidad": "mw",
        "p3": "anual",
    })
    sd = engine.score(req).get("auto_cuantificacion")
    assert sd.raw_answers["pct_varada_calculado"] == pytest.approx(30.0)


def test_auto_cuant_pct_varada_none_sin_datos(engine):
    req = _req(auto_cuantificacion={
        "p1_capacidad_total": None,
        "p2_capacidad_utilizable": None,
        "unidad": "kw",
        "p3": "nunca_remedido",
    })
    sd = engine.score(req).get("auto_cuantificacion")
    assert sd.raw_answers["pct_varada_calculado"] is None


# ── Bloqueantes — fórmula (cantidad + score_p2) / 2 ──────────────────────────

def test_bloqueantes_caso_borde_solo_nada(engine):
    """Solo 'nada' → score_cantidad=100, p2=100 → score=100."""
    req = _req(bloqueantes={"p1_bloqueantes": ["nada"], "p2_severidad": None})
    sd = engine.score(req).get("bloqueantes")
    assert sd.score == pytest.approx(100.0)
    assert "nada" in sd.notas[0]


def test_bloqueantes_un_bloqueante(engine):
    """1 bloqueante (→67) + moderado (→67) → (67+67)/2 = 67"""
    req = _req(bloqueantes={"p1_bloqueantes": ["presupuesto"], "p2_severidad": "moderado"})
    sd = engine.score(req).get("bloqueantes")
    assert sd.desglose["score_cantidad_p1"] == 67
    assert sd.desglose["p2"] == 67
    assert sd.score == pytest.approx(67.0)


def test_bloqueantes_dos_bloqueantes(engine):
    """2 bloqueantes (→33) + fuerte (→33) → (33+33)/2 = 33"""
    req = _req(bloqueantes={
        "p1_bloqueantes": ["presupuesto", "herramientas"],
        "p2_severidad": "fuerte",
    })
    sd = engine.score(req).get("bloqueantes")
    assert sd.desglose["score_cantidad_p1"] == 33
    assert sd.score == pytest.approx(33.0)


def test_bloqueantes_tres_o_mas(engine):
    """3 bloqueantes (→0) + estructural (→0) → 0"""
    req = _req(bloqueantes={
        "p1_bloqueantes": ["presupuesto", "herramientas", "personal"],
        "p2_severidad": "estructural",
    })
    sd = engine.score(req).get("bloqueantes")
    assert sd.score == pytest.approx(0.0)


def test_bloqueantes_p1_guardado_en_raw(engine):
    req = _req(bloqueantes={
        "p1_bloqueantes": ["autoridad_politica", "personal"],
        "p2_severidad": "moderado",
    })
    sd = engine.score(req).get("bloqueantes")
    assert "autoridad_politica" in sd.raw_answers["p1_bloqueantes"]


# ── Determinismo ──────────────────────────────────────────────────────────────

def test_mismo_input_mismo_output(engine):
    req = _req()
    r1 = engine.score(req)
    r2 = engine.score(req)
    for d in ["latencia", "visibilidad", "atribucion_friccion",
              "auto_cuantificacion", "bloqueantes"]:
        assert r1.get(d).score == r2.get(d).score
