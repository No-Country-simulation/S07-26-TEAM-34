"""
Tests PR 2 — Schemas Pydantic de entrada (backlog sección 9, doc metodológico §3-8).

Cubre: caso válido, campo faltante, valores límite, casos borde documentados.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.request import (
    CuestionarioRequest,
    RespuestasAtribucion,
    RespuestasAutoCuantificacion,
    RespuestasBloqueantes,
    RespuestasLatencia,
    RespuestasVisibilidad,
)


# ── Payload completo válido ───────────────────────────────────────────────────

def _payload_valido() -> dict:
    return {
        "contexto": {
            "facility_size": "1-5MW",
            "region": "Latinoamerica",
            "dc_type": "colocation",
        },
        "latencia": {
            "p1_minutos": 8.0,
            "p2_minutos": 20.0,
            "p3": "alertas_manual",
        },
        "visibilidad": {
            "p1_sistemas": 2,
            "p2": "diario",
            "p3": "un_rol",
        },
        "atribucion_friccion": {
            "p1": "energia_cooling",
            "p2": "estimacion",
            "p3": "revision_periodica",
        },
        "auto_cuantificacion": {
            "p1_capacidad_total": 5.0,
            "p2_capacidad_utilizable": 3.5,
            "unidad": "mw",
            "p3": "anual",
        },
        "bloqueantes": {
            "p1_bloqueantes": ["presupuesto"],
            "p2_severidad": "moderado",
        },
    }


def test_cuestionario_completo_valido():
    req = CuestionarioRequest(**_payload_valido())
    assert req.contexto.region == "Latinoamerica"
    assert req.latencia.p1_minutos == 8.0
    assert req.bloqueantes.p1_bloqueantes == ["presupuesto"]


# ── Campos obligatorios ───────────────────────────────────────────────────────

def test_falta_contexto_falla():
    data = _payload_valido()
    del data["contexto"]
    with pytest.raises(ValidationError) as exc:
        CuestionarioRequest(**data)
    assert "contexto" in str(exc.value)


def test_falta_dimension_completa_falla():
    data = _payload_valido()
    del data["latencia"]
    with pytest.raises(ValidationError):
        CuestionarioRequest(**data)


# ── Latencia — inputs numéricos ───────────────────────────────────────────────

def test_latencia_minutos_cero_valido():
    """0 minutos es válido (ajuste instantáneo — score máximo)."""
    r = RespuestasLatencia(p1_minutos=0, p2_minutos=0, p3="automatizado")
    assert r.p1_minutos == 0.0


def test_latencia_minutos_negativos_falla():
    with pytest.raises(ValidationError):
        RespuestasLatencia(p1_minutos=-1, p2_minutos=10, p3="automatizado")


def test_latencia_p3_invalido_falla():
    with pytest.raises(ValidationError):
        RespuestasLatencia(p1_minutos=5, p2_minutos=5, p3="opcion_inexistente")


def test_latencia_limite_bucket_5_min():
    """5 minutos → bucket de score 100; 6 minutos → bucket de score 75."""
    r5 = RespuestasLatencia(p1_minutos=5, p2_minutos=5, p3="automatizado")
    r6 = RespuestasLatencia(p1_minutos=6, p2_minutos=6, p3="automatizado")
    assert r5.p1_minutos == 5.0
    assert r6.p1_minutos == 6.0


# ── Visibilidad — input numérico ──────────────────────────────────────────────

def test_visibilidad_sistemas_cero_valido():
    """0 sistemas = sin sistema definido → score 0, pero el schema lo acepta."""
    r = RespuestasVisibilidad(p1_sistemas=0, p2="nunca", p3="nadie")
    assert r.p1_sistemas == 0


def test_visibilidad_sistemas_negativo_falla():
    with pytest.raises(ValidationError):
        RespuestasVisibilidad(p1_sistemas=-1, p2="diario", p3="nadie")


def test_visibilidad_p2_invalido_falla():
    with pytest.raises(ValidationError):
        RespuestasVisibilidad(p1_sistemas=2, p2="bimensual", p3="nadie")


# ── Atribución — caso borde "no_sabria_decir" ───────────────────────────────────────

def test_atribucion_no_sabria_se_acepta():
    """Cuando p1='no_sabria_decir', se acepta; el engine asignará p2/p3=0."""
    r = RespuestasAtribucion(p1="no_sabria_decir", p2="sin_evidencia", p3="nunca_revisada")
    assert r.p1 == "no_sabria_decir"


def test_atribucion_p1_invalido_falla():
    with pytest.raises(ValidationError):
        RespuestasAtribucion(p1="interfaz_inexistente", p2="con_medicion", p3="revision_activa")


# ── Auto-cuantificación — coherencia P1/P2 ───────────────────────────────────

def test_auto_cuant_coherente_valido():
    r = RespuestasAutoCuantificacion(
        p1_capacidad_total=10.0,
        p2_capacidad_utilizable=7.5,
        unidad="mw",
        p3="anual",
    )
    assert r.p1_capacidad_total == 10.0


def test_auto_cuant_p2_mayor_p1_falla():
    """Caso borde doc §6: P2 > P1 es incoherente → falla."""
    with pytest.raises(ValidationError) as exc:
        RespuestasAutoCuantificacion(
            p1_capacidad_total=5.0,
            p2_capacidad_utilizable=8.0,  # mayor que p1
            unidad="mw",
            p3="anual",
        )
    assert "capacidad" in str(exc.value).lower()


def test_auto_cuant_ambos_none_valido():
    """Si no se proveen ambos valores, no hay coherencia que validar."""
    r = RespuestasAutoCuantificacion(
        p1_capacidad_total=None,
        p2_capacidad_utilizable=None,
        unidad="kw",
        p3="nunca_remedido",
    )
    assert r.p1_capacidad_total is None


def test_auto_cuant_p1_cero_p2_cero_valido():
    """P1=0 y P2=0 es coherente (P2 <= P1)."""
    r = RespuestasAutoCuantificacion(
        p1_capacidad_total=0.0,
        p2_capacidad_utilizable=0.0,
        unidad="mw",
        p3="nunca_remedido",
    )
    assert r.p2_capacidad_utilizable == 0.0


def test_auto_cuant_unidad_invalida_falla():
    with pytest.raises(ValidationError):
        RespuestasAutoCuantificacion(
            p1_capacidad_total=5.0,
            p2_capacidad_utilizable=3.0,
            unidad="toneladas",   # no está en el enum
            p3="anual",
        )


# ── Bloqueantes — multi-selección y caso borde "nada" ───────────────────────

def test_bloqueantes_uno_valido():
    r = RespuestasBloqueantes(
        p1_bloqueantes=["presupuesto"],
        p2_severidad="moderado",
    )
    assert r.p1_bloqueantes == ["presupuesto"]


def test_bloqueantes_multiples_valido():
    r = RespuestasBloqueantes(
        p1_bloqueantes=["presupuesto", "herramientas"],
        p2_severidad="fuerte",
    )
    assert len(r.p1_bloqueantes) == 2


def test_bloqueantes_solo_nada_sin_p2_valido():
    """Caso borde doc §7: solo 'nada' → p2 no requerido, engine asigna 100."""
    r = RespuestasBloqueantes(p1_bloqueantes=["nada"], p2_severidad=None)
    assert r.p1_bloqueantes == ["nada"]
    assert r.p2_severidad is None


def test_bloqueantes_nada_con_otros_falla():
    """'nada' no puede combinarse con otros bloqueantes."""
    with pytest.raises(ValidationError) as exc:
        RespuestasBloqueantes(
            p1_bloqueantes=["nada", "presupuesto"],
            p2_severidad="moderado",
        )
    assert "nada" in str(exc.value).lower()


def test_bloqueantes_sin_p1_falla():
    with pytest.raises(ValidationError):
        RespuestasBloqueantes(p1_bloqueantes=[], p2_severidad="moderado")


def test_bloqueantes_sin_p2_cuando_hay_bloqueante_falla():
    """Si hay bloqueantes distintos a 'nada', p2 es obligatorio."""
    with pytest.raises(ValidationError):
        RespuestasBloqueantes(
            p1_bloqueantes=["presupuesto"],
            p2_severidad=None,
        )


def test_bloqueantes_opcion_invalida_falla():
    with pytest.raises(ValidationError):
        RespuestasBloqueantes(
            p1_bloqueantes=["opcion_inexistente"],
            p2_severidad="moderado",
        )


# ── Contexto — opciones ───────────────────────────────────────────────────────

def test_contexto_facility_size_invalido_falla():
    data = _payload_valido()
    data["contexto"]["facility_size"] = "gigante"
    with pytest.raises(ValidationError):
        CuestionarioRequest(**data)


def test_contexto_dc_type_invalido_falla():
    data = _payload_valido()
    data["contexto"]["dc_type"] = "nube"
    with pytest.raises(ValidationError):
        CuestionarioRequest(**data)
