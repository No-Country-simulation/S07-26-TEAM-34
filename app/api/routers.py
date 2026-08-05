"""
Routers FastAPI — reciben, llaman al orquestador, devuelven.
No calculan nada.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.request import CuestionarioRequest
from app.schemas.response import PDFInputResponse, ResultadoResponse
from app.services.benchmark_service import BenchmarkService

router = APIRouter()
_service = BenchmarkService()


@router.post("/respuestas", response_model=ResultadoResponse, status_code=202)
def enviar_respuestas(req: CuestionarioRequest) -> ResultadoResponse:
    """Recibe el cuestionario completo y ejecuta el pipeline."""
    return _service.procesar(req)


@router.get("/resultados/{operator_id}", response_model=ResultadoResponse)
def obtener_resultado(operator_id: str) -> ResultadoResponse:
    """Devuelve el resultado calculado para un operador."""
    # TODO: leer desde DB en PR de persistencia
    raise HTTPException(status_code=404, detail="Resultado no encontrado")


@router.get("/resultados/{operator_id}/pdf", response_model=PDFInputResponse)
def obtener_pdf_input(operator_id: str) -> PDFInputResponse:
    """JSON estable para que Proyecto 5 genere el PDF."""
    # TODO: leer desde DB en PR de persistencia
    raise HTTPException(status_code=404, detail="Resultado no encontrado")
