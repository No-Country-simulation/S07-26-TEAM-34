"""
Schemas de salida — lo que devuelve la API.

ResultadoResponse: resultado completo para la web.
PDFInputResponse:  JSON estable para que el Proyecto 5 genere el PDF.
"""
from __future__ import annotations

from pydantic import BaseModel


class ScoreDimension(BaseModel):
    dimension: str
    score: float                  # 0-100
    percentil: float              # 0-100
    descripcion_breve: str


class ResultadoResponse(BaseModel):
    operator_id: str
    perfil: str                                    # ej. "operacion_reactiva"
    friccion_principal: str                        # dimensión con percentil más bajo
    scores: list[ScoreDimension]
    top_quartile_gaps: dict[str, str]              # dimensión → descripción del gap
    diagnostico_texto: str                         # texto redactado por el LLM
    porcentaje_capacidad_varada: float | None      # calculado si P1/P2 son coherentes
    benchmark_version: str
    dimension_version: str


class PDFInputResponse(BaseModel):
    """
    Payload estable para el Proyecto 5.
    No recalcula nada — es lo que ya está en la tabla results.
    """
    operator_id: str
    perfil: str
    friccion_principal: str
    scores: list[ScoreDimension]
    top_quartile_gaps: dict[str, str]
    diagnostico_texto: str
    porcentaje_capacidad_varada: float | None
    benchmark_version: str
    dimension_version: str
