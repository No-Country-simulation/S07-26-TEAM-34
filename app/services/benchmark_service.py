"""
Orquestador (services/) — llama a los motores en el orden del backlog (sección 8).

Recibe datos, devuelve datos.
No importa FastAPI. No sabe nada de HTTP. Testeable sin servidor.

Orden de ejecución:
  Scoring (3.1)
  → Grupos comparables (3.2)
  → Rebalanceo (3.3) → Benchmark y percentiles (3.4)
  → Comparación top 25% (3.5)
  → Interpretación con LLM (3.6)
  → Privacidad y agregación (3.7) → Dataset primario

Los motores que todavía no están implementados usan placeholders
que devuelven datos válidos para no bloquear la integración.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.schemas.request import CuestionarioRequest
from app.schemas.response import PDFInputResponse, ResultadoResponse, ScoreDimension


# ── Resultado intermedio que viaja entre motores ──────────────────────────────

@dataclass
class PipelineResult:
    operator_id: str
    scores: dict[str, float] = field(default_factory=dict)        # dim → 0-100
    raw_answers: dict[str, dict] = field(default_factory=dict)    # dim → respuestas crudas
    grupo_comparable: str = "global"
    n_grupo: int = 0
    peso_publico: float = 1.0
    peso_primario: float = 0.0
    percentiles: dict[str, float] = field(default_factory=dict)   # dim → 0-100
    friccion_principal: str = ""
    perfil: str = ""
    top_quartile_gaps: dict[str, str] = field(default_factory=dict)
    diagnostico_texto: str = ""
    porcentaje_capacidad_varada: float | None = None
    benchmark_version: str = "1.0.0"
    dimension_version: str = "1.0.0"


# ── Imports de motores (placeholders hasta que se implementen en Tanda 2) ─────

def _scoring_engine(req: CuestionarioRequest, result: PipelineResult) -> None:
    """Motor 3.1 — placeholder hasta PR 6."""
    # TODO: implementar en PR 6
    for dim in ["latencia", "visibilidad", "atribucion_friccion",
                "auto_cuantificacion", "bloqueantes"]:
        result.scores[dim] = 50.0   # valor neutro hasta implementación real
    result.raw_answers = {
        "latencia": {"p1_minutos": req.latencia.p1_minutos,
                     "p2_minutos": req.latencia.p2_minutos,
                     "p3": req.latencia.p3},
        "visibilidad": {"p1_sistemas": req.visibilidad.p1_sistemas,
                        "p2": req.visibilidad.p2,
                        "p3": req.visibilidad.p3},
        "atribucion_friccion": {"p1": req.atribucion_friccion.p1,
                                "p2": req.atribucion_friccion.p2,
                                "p3": req.atribucion_friccion.p3},
        "auto_cuantificacion": {"p1": req.auto_cuantificacion.p1_capacidad_total,
                                "p2": req.auto_cuantificacion.p2_capacidad_utilizable,
                                "unidad": req.auto_cuantificacion.unidad,
                                "p3": req.auto_cuantificacion.p3},
        "bloqueantes": {"p1": req.bloqueantes.p1_bloqueantes,
                        "p2": req.bloqueantes.p2_severidad},
    }


def _grupos_comparables_engine(req: CuestionarioRequest, result: PipelineResult) -> None:
    """Motor 3.2 — placeholder hasta Tanda 2."""
    # TODO: implementar con dataset sintético
    ctx = req.contexto
    result.grupo_comparable = f"{ctx.region}_{ctx.facility_size}_{ctx.dc_type}"
    result.n_grupo = 0   # sin dataset todavía


def _rebalanceo_engine(result: PipelineResult) -> None:
    """Motor 3.3 — placeholder hasta PR 10."""
    # TODO: peso_primario = (n_válido / (n_válido + 50)) × factor_diversidad
    result.peso_primario = 0.0
    result.peso_publico = 1.0


def _benchmark_engine(result: PipelineResult) -> None:
    """Motor 3.4 — placeholder hasta Tanda 2."""
    # TODO: calcular percentiles contra distribución combinada
    for dim in result.scores:
        result.percentiles[dim] = 50.0   # percentil neutro


def _top_quartile_engine(result: PipelineResult) -> None:
    """Motor 3.5 — placeholder hasta Tanda 2."""
    # TODO: comparar respuestas del operador vs. top 25%
    result.top_quartile_gaps = {}


def _interpretacion_engine(result: PipelineResult) -> None:
    """Motor 3.6 — placeholder hasta Tanda 2."""
    # TODO: asignar perfil por regla determinística, luego LLM para texto
    if result.percentiles:
        peor_dim = min(result.percentiles, key=result.percentiles.get)
        result.friccion_principal = peor_dim
    else:
        result.friccion_principal = "latencia"
    result.perfil = "pendiente_de_implementacion"
    result.diagnostico_texto = "Diagnóstico pendiente de implementación del motor de interpretación."


def _privacidad_engine(result: PipelineResult) -> None:
    """Motor 3.7 — UUID ya asignado. Nada más en la versión liviana."""
    pass   # el operator_id es aleatorio desde el inicio del pipeline


# ── Orquestador principal ─────────────────────────────────────────────────────

class BenchmarkService:
    """
    Orquesta los motores en el orden del backlog sección 8.
    No importa FastAPI. Recibe CuestionarioRequest, devuelve ResultadoResponse.
    """

    def procesar(self, req: CuestionarioRequest) -> ResultadoResponse:
        result = PipelineResult(operator_id=str(uuid.uuid4()))

        # Orden exacto del backlog sección 8
        _scoring_engine(req, result)
        _grupos_comparables_engine(req, result)
        _rebalanceo_engine(result)
        _benchmark_engine(result)
        _top_quartile_engine(result)
        _interpretacion_engine(result)
        _privacidad_engine(result)

        # Cálculo derivado de capacidad varada (doc §6)
        p1 = req.auto_cuantificacion.p1_capacidad_total
        p2 = req.auto_cuantificacion.p2_capacidad_utilizable
        if p1 and p2 and p1 > 0:
            result.porcentaje_capacidad_varada = round((p1 - p2) / p1 * 100, 2)

        return self._to_response(result)

    def pdf_input(self, req: CuestionarioRequest) -> PDFInputResponse:
        """Genera el payload para el PDF de Proyecto 5."""
        resultado = self.procesar(req)
        return PDFInputResponse(**resultado.model_dump())

    # ── privado ───────────────────────────────────────────────────────────────

    @staticmethod
    def _to_response(r: PipelineResult) -> ResultadoResponse:
        scores = [
            ScoreDimension(
                dimension=dim,
                score=score,
                percentil=r.percentiles.get(dim, 50.0),
                descripcion_breve="",
            )
            for dim, score in r.scores.items()
        ]
        return ResultadoResponse(
            operator_id=r.operator_id,
            perfil=r.perfil,
            friccion_principal=r.friccion_principal,
            scores=scores,
            top_quartile_gaps=r.top_quartile_gaps,
            diagnostico_texto=r.diagnostico_texto,
            porcentaje_capacidad_varada=r.porcentaje_capacidad_varada,
            benchmark_version=r.benchmark_version,
            dimension_version=r.dimension_version,
        )
