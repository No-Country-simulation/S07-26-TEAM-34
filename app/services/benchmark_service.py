"""
Orquestador — llama a los 7 motores en el orden del backlog (sección 8).

Flujo completo:
  Scoring → Grupos comparables → Rebalanceo → Benchmark/Percentiles
  → Top 25% → Interpretación → Privacidad/Persistencia

Recibe CuestionarioRequest, devuelve ResultadoResponse.
No importa FastAPI. No sabe nada de HTTP.
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Any

from app.config.loader import get_config
from app.engines.benchmark_engine import BenchmarkEngine
from app.engines.interpretation_engine import InterpretationEngine
from app.engines.privacy_engine import PrivacyEngine
from app.engines.rebalance_engine import RebalanceEngine
from app.engines.scoring_engine import ScoringEngine
from app.engines.top_quartile_engine import TopQuartileEngine
from app.models.database import get_session
from app.repositories.benchmark_repository import BenchmarkRepository
from app.schemas.request import CuestionarioRequest
from app.schemas.response import PDFInputResponse, ResultadoResponse, ScoreDimension


def _cargar_dataset_publico() -> dict[str, list[float]]:
    """
    Carga el dataset público sintético desde dimension_scores (source=public_synthetic).
    Si no hay datos, devuelve un dataset vacío por dimensión.
    """
    dataset: dict[str, list[float]] = {
        dim: [] for dim in ["latencia", "visibilidad", "atribucion_friccion",
                           "auto_cuantificacion", "bloqueantes"]
    }
    
    try:
        with get_session() as session:
            from app.models.tables import DimensionScore, SourceEnum, Operator
            
            # Obtener scores públicos por dimensión
            scores_publicos = session.query(DimensionScore.score, DimensionScore.dimension)\
                .join(Operator, Operator.id == DimensionScore.operator_id)\
                .filter(Operator.source == SourceEnum.public_synthetic)\
                .all()
            
            for score, dimension in scores_publicos:
                if dimension.value in dataset:
                    dataset[dimension.value].append(score)
                    
    except Exception as e:
        print(f"Error cargando dataset público: {e}")
        # Dataset vacío por defecto
        pass
    
    return dataset

_GRUPO_DEFAULT = "global"
_BENCHMARK_VERSION = "1.0.0"
_DIMENSION_VERSION = "1.0.0"


class BenchmarkService:
    """
    Orquesta los 7 motores en el orden del backlog §8.
    llm_client es opcional — si no se pasa, la interpretación usa fallback determinista.
    """

    def __init__(self, llm_client: Any | None = None) -> None:
        self._scoring = ScoringEngine()
        self._rebalanceo = RebalanceEngine()
        self._benchmark = BenchmarkEngine()
        self._top_quartile = TopQuartileEngine()
        self._interpretacion = InterpretationEngine(llm_client=llm_client)
        self._privacidad = PrivacyEngine()
        self._repo = BenchmarkRepository()
        self._cfg = get_config()

    def procesar(self, req: CuestionarioRequest) -> ResultadoResponse:
        # ── 1. Privacidad: ID anónimo al inicio (motor 3.7) ──────────────────
        operator_id = self._privacidad.generar_operator_id()

        # ── 2. Scoring (motor 3.1) ────────────────────────────────────────────
        scoring_result = self._scoring.score(req)
        scores = {sd.dimension: sd.score for sd in scoring_result.scores}
        raw_answers = {sd.dimension: sd.raw_answers for sd in scoring_result.scores}

        # ── 3. Grupos comparables (motor 3.2) — placeholder simple ────────────
        grupo = _GRUPO_DEFAULT   # TODO: segmentar por region/facility_size/dc_type

        # ── 4. Cargar dataset público desde BD (PR 1) ────────────────────────
        dataset_publico = _cargar_dataset_publico()

        # ── 5. Rebalanceo (motor 3.3) ─────────────────────────────────────────
        # Sin datos primarios al inicio → 100% público (doc §9)
        rebalanceo_por_dim = {}
        distribuciones = {}
        for dim in scores:
            rb = self._rebalanceo.rebalancear(
                scores_publicos=dataset_publico.get(dim, []),
                scores_primarios=[],   # dataset primario vacío al inicio
                categorias_cubiertas=0,
            )
            rebalanceo_por_dim[dim] = rb
            distribuciones[dim] = rb.distribucion_combinada

        # ── 5. Benchmark y percentiles (motor 3.4) ────────────────────────────
        benchmark_result = self._benchmark.calcular(
            scores_operador=scores,
            distribuciones=distribuciones,
            grupo_comparable=grupo,
        )
        percentiles = {pd.dimension: pd.percentil for pd in benchmark_result.dimensiones}
        umbrales_p75 = {pd.dimension: pd.p75_ref for pd in benchmark_result.dimensiones}

        # ── 6. Comparación top 25% (motor 3.5) ───────────────────────────────
        top_quartile_result = self._top_quartile.analizar(
            scores_operador=scores,
            percentiles_operador=percentiles,
            umbrales_p75=umbrales_p75,
        )
        gaps = {b.dimension: b.descripcion for b in top_quartile_result.brechas}

        # ── 7. Interpretación (motor 3.6) ─────────────────────────────────────
        interp = self._interpretacion.interpretar(scores, benchmark_result, top_quartile_result)

        # ── 8. Cálculo derivado: % capacidad varada ───────────────────────────
        p1 = req.auto_cuantificacion.p1_capacidad_total
        p2 = req.auto_cuantificacion.p2_capacidad_utilizable
        pct_varada = round((p1 - p2) / p1 * 100, 2) if p1 and p2 and p1 > 0 else None

        # ── 9. Persistencia (3 tablas) ────────────────────────────────────────
        with get_session() as session:
            self._repo.guardar_resultado(
                session=session,
                operator_id=operator_id,
                contexto=req.contexto.model_dump(),
                scores=scores,
                raw_answers=raw_answers,
                percentiles=percentiles,
                friccion_principal=interp.friccion_principal,
                perfil=interp.perfil,
                top_quartile_gaps=gaps,
                diagnostico_texto=interp.diagnostico_texto,
                benchmark_version=_BENCHMARK_VERSION,
                dimension_version=_DIMENSION_VERSION,
            )

        return ResultadoResponse(
            operator_id=operator_id,
            perfil=interp.perfil,
            friccion_principal=interp.friccion_principal,
            scores=[
                ScoreDimension(
                    dimension=dim,
                    score=score,
                    percentil=percentiles.get(dim, 50.0),
                    descripcion_breve="",
                )
                for dim, score in scores.items()
            ],
            top_quartile_gaps=gaps,
            diagnostico_texto=interp.diagnostico_texto,
            porcentaje_capacidad_varada=pct_varada,
            benchmark_version=_BENCHMARK_VERSION,
            dimension_version=_DIMENSION_VERSION,
        )

    def pdf_input(self, operator_id: str) -> PDFInputResponse | None:
        """Lee el resultado ya calculado desde DB (no recalcula)."""
        with get_session() as session:
            result = self._repo.obtener_resultado(session, operator_id)
            if result is None:
                return None
            return PDFInputResponse(
                operator_id=operator_id,
                perfil=result.profile,
                friccion_principal=result.friccion_principal,
                scores=[
                    ScoreDimension(
                        dimension=k,
                        score=0.0,
                        percentil=v,
                        descripcion_breve="",
                    )
                    for k, v in result.percentiles.items()
                ],
                top_quartile_gaps=result.top_quartile_gaps,
                diagnostico_texto=result.diagnostico_texto,
                porcentaje_capacidad_varada=None,
                benchmark_version=_BENCHMARK_VERSION,
                dimension_version=_DIMENSION_VERSION,
            )
