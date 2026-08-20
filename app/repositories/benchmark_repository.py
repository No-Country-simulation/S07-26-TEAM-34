"""
Repositorio — guarda y lee de las 3 tablas (backlog §11).

Separado del cálculo (engines) y de la orquestación (services).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.tables import DimensionScore, DimensionEnum, Operator, Result, SourceEnum


class BenchmarkRepository:

    def guardar_resultado(
        self,
        session: Session,
        operator_id: str,
        contexto: dict,
        scores: dict[str, float],
        raw_answers: dict[str, dict],
        percentiles: dict[str, float],
        friccion_principal: str,
        perfil: str,
        top_quartile_gaps: dict[str, str],
        diagnostico_texto: str,
        benchmark_version: str,
        dimension_version: str,
        diagnostico_meta: dict | None = None,
    ) -> None:
        """Persiste las 3 tablas en una sola transacción."""

        # operators
        op = Operator(
            id=operator_id,
            source=SourceEnum.primary,
            region=contexto.get("region"),
            facility_size=contexto.get("facility_size"),
            dc_type=contexto.get("dc_type"),
            benchmark_version=benchmark_version,
            dimension_version=dimension_version,
        )
        session.add(op)

        # dimension_scores — 5 filas
        for dim_str, score in scores.items():
            session.add(DimensionScore(
                operator_id=operator_id,
                dimension=DimensionEnum(dim_str),
                score=round(score, 2),
                raw_answers=raw_answers.get(dim_str, {}),
            ))

        # results
        session.add(Result(
            operator_id=operator_id,
            percentiles=percentiles,
            friccion_principal=friccion_principal,
            profile=perfil,
            top_quartile_gaps=top_quartile_gaps,
            diagnostico_texto=diagnostico_texto,
            diagnostico_meta=diagnostico_meta,
        ))

    def obtener_resultado(self, session: Session, operator_id: str) -> Result | None:
        return session.get(Result, operator_id)
