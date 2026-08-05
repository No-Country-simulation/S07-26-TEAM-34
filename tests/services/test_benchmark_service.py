"""
Tests PR 4 — Orquestador (backlog sección 8, PR guide Tanda 1 PR 4).

Cubre: orden correcto de motores, propagación de excepciones,
resultado tiene las dimensiones correctas, cálculo de capacidad varada.
No levanta servidor HTTP.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, call

from app.schemas.request import CuestionarioRequest
from app.services.benchmark_service import BenchmarkService


def _req(**overrides) -> CuestionarioRequest:
    data = {
        "contexto": {"facility_size": "5_20mw", "region": "europa", "dc_type": "enterprise"},
        "latencia": {"p1_minutos": 30.0, "p2_minutos": 45.0, "p3": "reporte_revision_manual"},
        "visibilidad": {"p1_sistemas": 3, "p2": "semanal", "p3": "nadie"},
        "atribucion_friccion": {"p1": "workload_energia", "p2": "sin_evidencia", "p3": "nunca"},
        "auto_cuantificacion": {
            "p1_capacidad_total": 10.0,
            "p2_capacidad_utilizable": 8.0,
            "unidad": "mw",
            "p3": "anual",
        },
        "bloqueantes": {"p1_bloqueantes": ["presupuesto", "herramientas"], "p2_severidad": "fuerte"},
    }
    data.update(overrides)
    return CuestionarioRequest(**data)


def test_servicio_devuelve_resultado():
    svc = BenchmarkService()
    resultado = svc.procesar(_req())
    assert resultado.operator_id
    assert resultado.friccion_principal
    assert len(resultado.scores) == 5


def test_servicio_cinco_dimensiones_en_scores():
    svc = BenchmarkService()
    resultado = svc.procesar(_req())
    dims = {s.dimension for s in resultado.scores}
    assert dims == {
        "latencia", "visibilidad", "atribucion_friccion",
        "auto_cuantificacion", "bloqueantes"
    }


def test_servicio_calcula_capacidad_varada():
    """(10 - 8) / 10 * 100 = 20%"""
    svc = BenchmarkService()
    resultado = svc.procesar(_req())
    assert resultado.porcentaje_capacidad_varada == pytest.approx(20.0)


def test_servicio_capacidad_varada_none_cuando_no_hay_p1():
    req = _req()
    req.auto_cuantificacion.p1_capacidad_total = None
    req.auto_cuantificacion.p2_capacidad_utilizable = None
    svc = BenchmarkService()
    resultado = svc.procesar(req)
    assert resultado.porcentaje_capacidad_varada is None


def test_servicio_operator_id_es_uuid():
    """Cada llamada genera un operator_id distinto."""
    svc = BenchmarkService()
    r1 = svc.procesar(_req())
    r2 = svc.procesar(_req())
    assert r1.operator_id != r2.operator_id


def test_servicio_versiones_registradas():
    svc = BenchmarkService()
    resultado = svc.procesar(_req())
    assert resultado.benchmark_version
    assert resultado.dimension_version


def test_servicio_no_importa_fastapi():
    """El servicio no tiene imports de FastAPI."""
    import importlib, inspect
    import app.services.benchmark_service as mod
    source = inspect.getsource(mod)
    # No debe haber ningún import de fastapi en el módulo
    assert "import fastapi" not in source.lower()
    assert "from fastapi" not in source.lower()


def test_servicio_excepcion_se_propaga():
    """Si un motor lanza excepción, no se traga en silencio."""
    svc = BenchmarkService()
    with patch("app.services.benchmark_service._scoring_engine",
               side_effect=RuntimeError("motor falló")):
        with pytest.raises(RuntimeError, match="motor falló"):
            svc.procesar(_req())


def test_servicio_motores_llamados_en_orden():
    """Los motores se llaman en el orden del backlog sección 8."""
    call_order = []

    def mock_scoring(req, result):
        call_order.append("scoring")
        result.scores = {d: 50.0 for d in
                         ["latencia", "visibilidad", "atribucion_friccion",
                          "auto_cuantificacion", "bloqueantes"]}

    def mock_grupos(req, result):
        call_order.append("grupos")

    def mock_rebalanceo(result):
        call_order.append("rebalanceo")

    def mock_benchmark(result):
        call_order.append("benchmark")
        result.percentiles = {d: 50.0 for d in result.scores}

    def mock_top_quartile(result):
        call_order.append("top_quartile")

    def mock_interpretacion(result):
        call_order.append("interpretacion")
        result.friccion_principal = "latencia"
        result.perfil = "test"
        result.diagnostico_texto = "test"

    def mock_privacidad(result):
        call_order.append("privacidad")

    with patch.multiple(
        "app.services.benchmark_service",
        _scoring_engine=mock_scoring,
        _grupos_comparables_engine=mock_grupos,
        _rebalanceo_engine=mock_rebalanceo,
        _benchmark_engine=mock_benchmark,
        _top_quartile_engine=mock_top_quartile,
        _interpretacion_engine=mock_interpretacion,
        _privacidad_engine=mock_privacidad,
    ):
        BenchmarkService().procesar(_req())

    assert call_order == [
        "scoring", "grupos", "rebalanceo", "benchmark",
        "top_quartile", "interpretacion", "privacidad"
    ]
