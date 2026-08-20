"""
Tests de integración — orquestador completo con todos los motores reales.

Verifica el flujo end-to-end: request → scores reales → percentiles → resultado persistido.
"""
from __future__ import annotations
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.models.database import Base
from app.models.tables import Operator, DimensionScore, Result
from app.main import app

client = TestClient(app)

_PAYLOAD = {
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


def test_flujo_completo_devuelve_202():
    resp = client.post("/api/v1/respuestas", json=_PAYLOAD)
    assert resp.status_code == 202


def test_resultado_tiene_scores_reales():
    """Los scores no son el placeholder 50.0 — son valores calculados."""
    resp = client.post("/api/v1/respuestas", json=_PAYLOAD)
    body = resp.json()
    scores = {s["dimension"]: s["score"] for s in body["scores"]}
    # latencia: p1=8min(75) + p2=20min(75) + alertas(67) / 3 = 72.33
    assert scores["latencia"] == pytest.approx(72.33, abs=0.1)


def test_resultado_tiene_percentiles():
    resp = client.post("/api/v1/respuestas", json=_PAYLOAD)
    body = resp.json()
    for score in body["scores"]:
        assert 0.0 <= score["percentil"] <= 100.0


def test_resultado_tiene_perfil():
    resp = client.post("/api/v1/respuestas", json=_PAYLOAD)
    body = resp.json()
    assert body["perfil"] in [
        "operacion_reactiva", "visibilidad_limitada",
        "coordinacion_parcial", "operacion_optimizada"
    ]


def test_resultado_tiene_friccion_principal():
    resp = client.post("/api/v1/respuestas", json=_PAYLOAD)
    body = resp.json()
    assert body["friccion_principal"] in [
        "latencia", "visibilidad", "atribucion_friccion",
        "auto_cuantificacion", "bloqueantes"
    ]


def test_capacidad_varada_calculada():
    """(10 - 7) / 10 * 100 = 30%"""
    resp = client.post("/api/v1/respuestas", json=_PAYLOAD)
    assert resp.json()["porcentaje_capacidad_varada"] == pytest.approx(30.0)


def test_versiones_registradas():
    resp = client.post("/api/v1/respuestas", json=_PAYLOAD)
    body = resp.json()
    assert body["benchmark_version"] == "1.0.0"
    assert body["dimension_version"] == "1.0.0"


def test_operator_id_es_uuid():
    resp = client.post("/api/v1/respuestas", json=_PAYLOAD)
    oid = resp.json()["operator_id"]
    assert uuid.UUID(oid).version == 4


def test_scores_caso_maximo():
    """Scores máximos: 0 min + automatizado + 1 sistema + tiempo_real, etc."""
    payload = {
        "contexto": {"facility_size": ">20MW", "region": "Europa", "dc_type": "hyperscale"},
        "latencia": {"p1_minutos": 0, "p2_minutos": 0, "p3": "automatizado"},
        "visibilidad": {"p1_sistemas": 1, "p2": "tiempo_real", "p3": "cualquiera"},
        "atribucion_friccion": {"p1": "energia_cooling", "p2": "con_medicion", "p3": "revision_activa"},
        "auto_cuantificacion": {
            "p1_capacidad_total": 10.0, "p2_capacidad_utilizable": 9.0,
            "unidad": "mw", "p3": "continuamente",
        },
        "bloqueantes": {"p1_bloqueantes": ["nada"], "p2_severidad": None},
    }
    resp = client.post("/api/v1/respuestas", json=payload)
    assert resp.status_code == 202
    scores = {s["dimension"]: s["score"] for s in resp.json()["scores"]}
    for dim, score in scores.items():
        assert score == pytest.approx(100.0, abs=0.1), f"{dim}: {score}"


def test_scores_caso_minimo():
    """Scores mínimos: todo al máximo de fricción."""
    payload = {
        "contexto": {"facility_size": "<1MW", "region": "Asia-Pacifico", "dc_type": "edge"},
        "latencia": {"p1_minutos": 2000, "p2_minutos": 2000, "p3": "sin_proceso"},
        "visibilidad": {"p1_sistemas": 10, "p2": "nunca", "p3": "nadie"},
        "atribucion_friccion": {"p1": "no_sabria_decir", "p2": "sin_evidencia", "p3": "nunca_revisada"},
        "auto_cuantificacion": {
            "p1_capacidad_total": None, "p2_capacidad_utilizable": None,
            "unidad": "kw", "p3": "nunca_remedido",
        },
        "bloqueantes": {
            "p1_bloqueantes": ["presupuesto", "herramientas", "personal"],
            "p2_severidad": "estructural",
        },
    }
    resp = client.post("/api/v1/respuestas", json=payload)
    assert resp.status_code == 202
    scores = {s["dimension"]: s["score"] for s in resp.json()["scores"]}
    for dim, score in scores.items():
        assert score == pytest.approx(0.0, abs=0.1), f"{dim}: {score}"
