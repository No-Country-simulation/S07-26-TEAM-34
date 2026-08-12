"""
Orquestador — motores en el orden del backlog (sección 8).
No importa FastAPI. No sabe nada de HTTP.
"""
from __future__ import annotations

import uuid
from typing import Any

from app.config.loader import get_config
from app.engines.benchmark_engine import BenchmarkEngine
from app.engines.interpretation_engine import InterpretationEngine
from app.engines.peer_group_engine import PeerGroupEngine
from app.engines.privacy_engine import PrivacyEngine
from app.engines.rebalance_engine import RebalanceEngine
from app.engines.scoring_engine import ScoringEngine
from app.engines.top_quartile_engine import TopQuartileEngine
from app.models.database import get_session
from app.repositories.benchmark_repository import BenchmarkRepository
from app.schemas.request import CuestionarioRequest
from app.schemas.response import PDFInputResponse, ResultadoResponse, ScoreDimension

_DIMENSIONES = ["latencia", "visibilidad", "atribucion_friccion",
                "auto_cuantificacion", "bloqueantes"]
_BENCHMARK_VERSION = "1.0.0"
_DIMENSION_VERSION = "1.0.0"


def _cargar_scores_por_source(source, grupo_id: str = "global") -> dict[str, list[float]]:
    """Carga scores filtrando por source y grupo comparable."""
    from app.models.tables import DimensionScore, Operator

    dataset: dict[str, list[float]] = {dim: [] for dim in _DIMENSIONES}
    with get_session() as session:
        q = session.query(DimensionScore.score, DimensionScore.dimension)\
            .join(Operator, Operator.id == DimensionScore.operator_id)\
            .filter(Operator.source == source)

        if grupo_id != "global":
            partes = grupo_id.split("|")
            if len(partes) == 3:
                q = q.filter(Operator.region == partes[0],
                             Operator.facility_size == partes[1],
                             Operator.dc_type == partes[2])
            elif len(partes) == 2:
                q = q.filter(Operator.facility_size == partes[0],
                             Operator.dc_type == partes[1])
            elif len(partes) == 1:
                q = q.filter(Operator.dc_type == partes[0])

        for score, dimension in q.all():
            if dimension.value in dataset:
                dataset[dimension.value].append(score)
    return dataset


def _contar_categorias_cubiertas_primarias() -> int:
    from app.models.tables import Operator, SourceEnum
    with get_session() as session:
        combinaciones = session.query(
            Operator.region, Operator.facility_size, Operator.dc_type
        ).filter(Operator.source == SourceEnum.primary).distinct().all()
    return len(combinaciones)


class BenchmarkService:
    def __init__(self, llm_client: Any | None = None) -> None:
        self._scoring = ScoringEngine()
        self._peer_group = PeerGroupEngine()
        self._rebalanceo = RebalanceEngine()
        self._benchmark = BenchmarkEngine()
        self._top_quartile = TopQuartileEngine()
        self._interpretacion = InterpretationEngine(llm_client=llm_client)
        self._privacidad = PrivacyEngine()
        self._repo = BenchmarkRepository()
        self._cfg = get_config()

    def procesar(self, req: CuestionarioRequest) -> ResultadoResponse:
        from app.models.tables import SourceEnum

        # 1. Privacidad: ID anónimo
        operator_id = self._privacidad.generar_operator_id()

        # 2. Scoring
        scoring_result = self._scoring.score(req)
        scores = {sd.dimension: sd.score for sd in scoring_result.scores}
        raw_answers = {sd.dimension: sd.raw_answers for sd in scoring_result.scores}

        # 3. Grupos comparables — usa datos reales de la DB
        with get_session() as session:
            peer = self._peer_group.seleccionar(
                facility_size=req.contexto.facility_size,
                region=req.contexto.region,
                dc_type=req.contexto.dc_type,
                session=session,
            )

        # 4. Dataset desde BD filtrado por grupo
        dataset_publico = _cargar_scores_por_source(SourceEnum.public_synthetic, peer.grupo_id)
        dataset_primario = _cargar_scores_por_source(SourceEnum.primary, peer.grupo_id)
        categorias_cubiertas = _contar_categorias_cubiertas_primarias()

        # 5. Rebalanceo
        distribuciones = {}
        for dim in scores:
            rb = self._rebalanceo.rebalancear(
                scores_publicos=dataset_publico.get(dim, []),
                scores_primarios=dataset_primario.get(dim, []),
                categorias_cubiertas=categorias_cubiertas,
            )
            distribuciones[dim] = rb.distribucion_combinada

        # 6. Benchmark y percentiles
        benchmark_result = self._benchmark.calcular(
            scores_operador=scores,
            distribuciones=distribuciones,
            grupo_comparable=peer.descripcion,
        )
        percentiles = {pd.dimension: pd.percentil for pd in benchmark_result.dimensiones}
        umbrales_p75 = {pd.dimension: pd.p75_ref for pd in benchmark_result.dimensiones}

        # 7. Top 25%
        top_quartile_result = self._top_quartile.analizar(
            scores_operador=scores,
            percentiles_operador=percentiles,
            umbrales_p75=umbrales_p75,
        )
        gaps = {b.dimension: b.descripcion for b in top_quartile_result.brechas}

        # 8. Interpretación
        interp = self._interpretacion.interpretar(
            scores, benchmark_result, top_quartile_result,
            raw_answers=raw_answers, contexto=req.contexto.model_dump(),
        )

        # 9. Capacidad varada
        p1 = req.auto_cuantificacion.p1_capacidad_total
        p2 = req.auto_cuantificacion.p2_capacidad_utilizable
        pct_varada = round((p1 - p2) / p1 * 100, 2) if p1 and p2 and p1 > 0 else None

        # 10. Persistencia
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
                    dimension=dim, score=score,
                    percentil=percentiles.get(dim, 50.0), descripcion_breve=""
                )
                for dim, score in scores.items()
            ],
            top_quartile_gaps=gaps,
            diagnostico_texto=interp.diagnostico_texto,
            porcentaje_capacidad_varada=pct_varada,
            benchmark_version=_BENCHMARK_VERSION,
            dimension_version=_DIMENSION_VERSION,
        )

    def obtener_resultado(self, operator_id: str) -> ResultadoResponse | None:
        with get_session() as session:
            result = self._repo.obtener_resultado(session, operator_id)
            if result is None:
                return None
            return ResultadoResponse(
                operator_id=operator_id,
                perfil=result.profile,
                friccion_principal=result.friccion_principal,
                scores=[
                    ScoreDimension(dimension=k, score=0.0, percentil=v, descripcion_breve="")
                    for k, v in result.percentiles.items()
                ],
                top_quartile_gaps=result.top_quartile_gaps,
                diagnostico_texto=result.diagnostico_texto,
                porcentaje_capacidad_varada=None,
                benchmark_version=_BENCHMARK_VERSION,
                dimension_version=_DIMENSION_VERSION,
            )

    def pdf_input(self, operator_id: str) -> PDFInputResponse | None:
        with get_session() as session:
            result = self._repo.obtener_resultado(session, operator_id)
            if result is None:
                return None
            return PDFInputResponse(
                operator_id=operator_id,
                perfil=result.profile,
                friccion_principal=result.friccion_principal,
                scores=[
                    ScoreDimension(dimension=k, score=0.0, percentil=v, descripcion_breve="")
                    for k, v in result.percentiles.items()
                ],
                top_quartile_gaps=result.top_quartile_gaps,
                diagnostico_texto=result.diagnostico_texto,
                porcentaje_capacidad_varada=None,
                benchmark_version=_BENCHMARK_VERSION,
                dimension_version=_DIMENSION_VERSION,
            )
