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
    mediana_ref: float             # mediana del grupo comparable (0-100)
    p75_ref: float                  # cuartil superior del grupo comparable (0-100)


class ResultadoResponse(BaseModel):
    operator_id: str
    perfil: str                                    # ej. "operacion_reactiva"
    friccion_principal: str                        # dimensión con percentil más bajo
    scores: list[ScoreDimension]
    top_quartile_gaps: dict[str, str]              # dimensión → descripción del gap
    titular: str                                    # hallazgo principal, 6-10 palabras
    diagnostico_texto: str                          # el razonamiento (nombre conservado por compatibilidad)
    accion_sugerida: str                            # qué observar a continuación
    confianza_nivel: str                            # "alto" | "medio" | "bajo"
    confianza_descripcion: str                      # por qué ese nivel de confianza
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
    titular: str
    diagnostico_texto: str
    accion_sugerida: str
    confianza_nivel: str
    confianza_descripcion: str
    porcentaje_capacidad_varada: float | None
    benchmark_version: str
    dimension_version: str
