"""
Routers FastAPI — reciben, llaman al orquestador, devuelven. No calculan nada.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException

from app.schemas.request import CuestionarioRequest
from app.schemas.response import PDFInputResponse, ResultadoResponse
from app.services.benchmark_service import BenchmarkService


def _construir_llm_client():
    """Gemini si hay API key configurada; si no, None → InterpretationEngine
    usa el fallback determinista (doc §7 — el sistema nunca falla por ausencia de LLM)."""
    if not os.environ.get("GEMINI_API_KEY"):
        return None
    from app.engines.llm_clients.gemini_client import GeminiClient
    return GeminiClient()


router = APIRouter()
_service = BenchmarkService(llm_client=_construir_llm_client())

_QUESTIONNAIRE_YAML_PATH = Path(__file__).parent.parent.parent / "config" / "questionnaire.yaml"


@router.get("/questionnaire")
def obtener_cuestionario() -> dict:
    """Devuelve config/questionnaire.yaml como JSON para que el frontend arme el formulario."""
    with open(_QUESTIONNAIRE_YAML_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


@router.post("/respuestas", response_model=ResultadoResponse, status_code=202)
def enviar_respuestas(req: CuestionarioRequest) -> ResultadoResponse:
    return _service.procesar(req)


@router.get("/resultados/{operator_id}", response_model=ResultadoResponse)
def obtener_resultado(operator_id: str) -> ResultadoResponse:
    """Devuelve el resultado calculado para un operador."""
    resultado = _service.obtener_resultado(operator_id)
    if resultado is None:
        raise HTTPException(status_code=404, detail="Resultado no encontrado")
    return resultado


@router.get("/resultados/{operator_id}/pdf", response_model=PDFInputResponse)
def obtener_pdf_input(operator_id: str) -> PDFInputResponse:
    """JSON estable para que Proyecto 5 genere el PDF."""
    resultado = _service.pdf_input(operator_id)
    if resultado is None:
        raise HTTPException(status_code=404, detail="Resultado no encontrado")
    return resultado
