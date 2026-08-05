"""
Tests PR 5 — Loader de config/dimensiones.yaml (backlog §9, doc metodológico §3-7).

Verifica que el YAML se carga correctamente y que los scores coinciden
exactamente con los definidos en el documento metodológico.
"""
from __future__ import annotations

import pytest

from app.config.loader import get_config


@pytest.fixture(autouse=True)
def clear_cache():
    get_config.cache_clear()
    yield
    get_config.cache_clear()


# ── Carga básica ──────────────────────────────────────────────────────────────

def test_config_carga_sin_error():
    cfg = get_config()
    assert cfg.version == "1.0.0"


def test_cinco_dimensiones_presentes():
    cfg = get_config()
    assert set(cfg.dimensiones.keys()) == {
        "latencia", "visibilidad", "atribucion_friccion",
        "auto_cuantificacion", "bloqueantes"
    }


def test_segmentacion_tiene_tres_campos():
    cfg = get_config()
    assert set(cfg.segmentacion._campos.keys()) == {
        "facility_size", "region", "dc_type"
    }


def test_facility_size_bandas_correctas():
    """Bandas del doc §8: <1MW, 1-5MW, 5-20MW, >20MW."""
    cfg = get_config()
    opciones = cfg.segmentacion.opciones("facility_size")
    assert opciones == ["menos_1mw", "1_5mw", "5_20mw", "mas_20mw"]


# ── Latencia — buckets numéricos (doc §3) ─────────────────────────────────────

def test_latencia_p1_bucket_0_5min():
    cfg = get_config()
    assert cfg.score_numerico("latencia", "p1", 0) == 100
    assert cfg.score_numerico("latencia", "p1", 5) == 100


def test_latencia_p1_bucket_6_60min():
    cfg = get_config()
    assert cfg.score_numerico("latencia", "p1", 6) == 75
    assert cfg.score_numerico("latencia", "p1", 60) == 75


def test_latencia_p1_bucket_61_240min():
    cfg = get_config()
    assert cfg.score_numerico("latencia", "p1", 61) == 50
    assert cfg.score_numerico("latencia", "p1", 240) == 50


def test_latencia_p1_bucket_241_1440min():
    cfg = get_config()
    assert cfg.score_numerico("latencia", "p1", 241) == 25
    assert cfg.score_numerico("latencia", "p1", 1440) == 25


def test_latencia_p1_bucket_mas_de_1440():
    cfg = get_config()
    assert cfg.score_numerico("latencia", "p1", 1441) == 0
    assert cfg.score_numerico("latencia", "p1", 99999) == 0


def test_latencia_p2_mismos_buckets_que_p1():
    """P2 tiene la misma escala que P1 (doc §3)."""
    cfg = get_config()
    for minutos, esperado in [(5, 100), (60, 75), (240, 50), (1440, 25), (1441, 0)]:
        assert cfg.score_numerico("latencia", "p2", minutos) == esperado


def test_latencia_p3_scores_correctos():
    """Escala 4 niveles: 100-67-33-0 (doc §3 y §2.3)."""
    cfg = get_config()
    assert cfg.score_categoria("latencia", "p3", "automatizado") == 100
    assert cfg.score_categoria("latencia", "p3", "alertas_accion_manual") == 67
    assert cfg.score_categoria("latencia", "p3", "reporte_revision_manual") == 33
    assert cfg.score_categoria("latencia", "p3", "sin_proceso") == 0


# ── Visibilidad — buckets enteros (doc §4) ────────────────────────────────────

def test_visibilidad_p1_1_sistema_score_100():
    cfg = get_config()
    assert cfg.score_numerico("visibilidad", "p1", 1) == 100


def test_visibilidad_p1_2_sistemas_score_67():
    cfg = get_config()
    assert cfg.score_numerico("visibilidad", "p1", 2) == 67


def test_visibilidad_p1_3_sistemas_score_33():
    cfg = get_config()
    assert cfg.score_numerico("visibilidad", "p1", 3) == 33


def test_visibilidad_p1_mas_de_3_score_0():
    cfg = get_config()
    assert cfg.score_numerico("visibilidad", "p1", 4) == 0
    assert cfg.score_numerico("visibilidad", "p1", 10) == 0


def test_visibilidad_p2_escala_5_niveles():
    """Escala 5 niveles: 100-75-50-25-0 (doc §4 y §2.3)."""
    cfg = get_config()
    assert cfg.score_categoria("visibilidad", "p2", "tiempo_real") == 100
    assert cfg.score_categoria("visibilidad", "p2", "diario") == 75
    assert cfg.score_categoria("visibilidad", "p2", "semanal") == 50
    assert cfg.score_categoria("visibilidad", "p2", "mensual") == 25
    assert cfg.score_categoria("visibilidad", "p2", "nunca") == 0


def test_visibilidad_p3_escala_3_niveles():
    """Escala 3 niveles: 100-50-0 (doc §4 y §2.3)."""
    cfg = get_config()
    assert cfg.score_categoria("visibilidad", "p3", "cualquier_responsable") == 100
    assert cfg.score_categoria("visibilidad", "p3", "rol_especifico") == 50
    assert cfg.score_categoria("visibilidad", "p3", "nadie") == 0


# ── Atribución — P1 nominal, P2 y P3 ordinales (doc §5) ──────────────────────

def test_atribucion_p1_es_nominal():
    cfg = get_config()
    p1 = cfg.dimension("atribucion_friccion").pregunta("p1")
    assert p1.es_nominal is True


def test_atribucion_p2_scores_correctos():
    """Escala 3 niveles: 100-50-0 (doc §5)."""
    cfg = get_config()
    assert cfg.score_categoria("atribucion_friccion", "p2", "con_evidencia") == 100
    assert cfg.score_categoria("atribucion_friccion", "p2", "estimacion") == 50
    assert cfg.score_categoria("atribucion_friccion", "p2", "sin_evidencia") == 0


def test_atribucion_p3_scores_correctos():
    cfg = get_config()
    assert cfg.score_categoria("atribucion_friccion", "p3", "activamente") == 100
    assert cfg.score_categoria("atribucion_friccion", "p3", "periodicamente") == 50
    assert cfg.score_categoria("atribucion_friccion", "p3", "nunca") == 0


# ── Auto-cuantificación — P1/P2 numéricos, P3 ordinal (doc §6) ───────────────

def test_auto_cuant_p1_p2_son_numericos():
    cfg = get_config()
    assert cfg.dimension("auto_cuantificacion").pregunta("p1").es_numerico is True
    assert cfg.dimension("auto_cuantificacion").pregunta("p2").es_numerico is True


def test_auto_cuant_p3_escala_4_niveles():
    """Escala 4 niveles: 100-67-33-0 (doc §6 y §2.3)."""
    cfg = get_config()
    assert cfg.score_categoria("auto_cuantificacion", "p3", "tiempo_real") == 100
    assert cfg.score_categoria("auto_cuantificacion", "p3", "trimestral_semestral") == 67
    assert cfg.score_categoria("auto_cuantificacion", "p3", "anual") == 33
    assert cfg.score_categoria("auto_cuantificacion", "p3", "nunca") == 0


# ── Bloqueantes — P1 nominal multi-selección, P2 ordinal (doc §7) ────────────

def test_bloqueantes_p1_es_nominal_multiseleccion():
    cfg = get_config()
    p1 = cfg.dimension("bloqueantes").pregunta("p1")
    assert p1.es_nominal is True
    assert p1.tipo == "categorico_nominal_multiseleccion"


def test_bloqueantes_score_por_cantidad_0():
    cfg = get_config()
    p1 = cfg.dimension("bloqueantes").pregunta("p1")
    assert p1.score_cantidad_bloqueantes(0) == 100


def test_bloqueantes_score_por_cantidad_1():
    cfg = get_config()
    p1 = cfg.dimension("bloqueantes").pregunta("p1")
    assert p1.score_cantidad_bloqueantes(1) == 67


def test_bloqueantes_score_por_cantidad_2():
    cfg = get_config()
    p1 = cfg.dimension("bloqueantes").pregunta("p1")
    assert p1.score_cantidad_bloqueantes(2) == 33


def test_bloqueantes_score_por_cantidad_3_o_mas():
    cfg = get_config()
    p1 = cfg.dimension("bloqueantes").pregunta("p1")
    assert p1.score_cantidad_bloqueantes(3) == 0
    assert p1.score_cantidad_bloqueantes(5) == 0


def test_bloqueantes_p2_escala_4_niveles():
    """Escala 4 niveles: 100-67-33-0 (doc §7 y §2.3)."""
    cfg = get_config()
    assert cfg.score_categoria("bloqueantes", "p2", "no_bloqueante") == 100
    assert cfg.score_categoria("bloqueantes", "p2", "moderado") == 67
    assert cfg.score_categoria("bloqueantes", "p2", "fuerte") == 33
    assert cfg.score_categoria("bloqueantes", "p2", "estructural") == 0


# ── Errores ───────────────────────────────────────────────────────────────────

def test_dimension_inexistente_lanza_error():
    cfg = get_config()
    with pytest.raises(KeyError, match="no existe"):
        cfg.dimension("dimension_inventada")


def test_opcion_invalida_lanza_error():
    cfg = get_config()
    with pytest.raises(KeyError, match="no existe"):
        cfg.score_categoria("latencia", "p3", "opcion_inventada")


def test_yaml_no_encontrado_lanza_error(tmp_path, monkeypatch):
    monkeypatch.setenv("DIMENSIONES_YAML", str(tmp_path / "no_existe.yaml"))
    get_config.cache_clear()
    with pytest.raises(FileNotFoundError):
        get_config()
