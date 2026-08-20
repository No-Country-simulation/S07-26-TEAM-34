"""
Tests PR 3 — FastAPI (backlog sección 9, PR guide sección Tanda 1 PR 3).

Cubre: 200 con payload válido, 422 con payload inválido, claves esperadas en respuesta.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_PAYLOAD_VALIDO = {
    "contexto": {"facility_size": "1-5MW", "region": "Latinoamerica", "dc_type": "colocation"},
    "latencia": {"p1_minutos": 8.0, "p2_minutos": 20.0, "p3": "alertas_manual"},
    "visibilidad": {"p1_sistemas": 2, "p2": "diario", "p3": "un_rol"},
    "atribucion_friccion": {"p1": "energia_cooling", "p2": "estimacion", "p3": "revision_periodica"},
    "auto_cuantificacion": {
        "p1_capacidad_total": 5.0,
        "p2_capacidad_utilizable": 3.5,
        "unidad": "mw",
        "p3": "anual",
    },
    "bloqueantes": {"p1_bloqueantes": ["presupuesto"], "p2_severidad": "moderado"},
}


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_enviar_respuestas_valido_200():
    resp = client.post("/api/v1/respuestas", json=_PAYLOAD_VALIDO)
    assert resp.status_code == 202


def test_enviar_respuestas_tiene_claves_esperadas():
    resp = client.post("/api/v1/respuestas", json=_PAYLOAD_VALIDO)
    body = resp.json()
    for key in ["operator_id", "perfil", "friccion_principal", "scores",
                "top_quartile_gaps", "diagnostico_texto", "benchmark_version"]:
        assert key in body, f"Falta clave: {key}"


def test_enviar_respuestas_scores_cinco_dimensiones():
    resp = client.post("/api/v1/respuestas", json=_PAYLOAD_VALIDO)
    body = resp.json()
    assert len(body["scores"]) == 5
    dims = {s["dimension"] for s in body["scores"]}
    assert dims == {
        "latencia", "visibilidad", "atribucion_friccion",
        "auto_cuantificacion", "bloqueantes"
    }


def test_enviar_respuestas_capacidad_varada_calculada():
    """P1=5, P2=3.5 → capacidad varada = (5-3.5)/5*100 = 30%"""
    resp = client.post("/api/v1/respuestas", json=_PAYLOAD_VALIDO)
    body = resp.json()
    assert body["porcentaje_capacidad_varada"] == pytest.approx(30.0)


def test_enviar_respuestas_payload_invalido_422():
    """Payload vacío → 422."""
    resp = client.post("/api/v1/respuestas", json={})
    assert resp.status_code == 422


def test_enviar_respuestas_minutos_negativos_422():
    payload = dict(_PAYLOAD_VALIDO)
    payload["latencia"] = {"p1_minutos": -5, "p2_minutos": 10, "p3": "automatizado"}
    resp = client.post("/api/v1/respuestas", json=payload)
    assert resp.status_code == 422


def test_enviar_respuestas_p2_mayor_p1_422():
    payload = dict(_PAYLOAD_VALIDO)
    payload["auto_cuantificacion"] = {
        "p1_capacidad_total": 3.0,
        "p2_capacidad_utilizable": 5.0,   # > p1
        "unidad": "mw",
        "p3": "anual",
    }
    resp = client.post("/api/v1/respuestas", json=payload)
    assert resp.status_code == 422


def test_obtener_resultado_no_existente_404():
    resp = client.get("/api/v1/resultados/uuid-inexistente")
    assert resp.status_code == 404


def test_obtener_pdf_no_existente_404():
    resp = client.get("/api/v1/resultados/uuid-inexistente/pdf")
    assert resp.status_code == 404
