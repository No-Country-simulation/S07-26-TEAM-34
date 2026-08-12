"""
Motor de grupos comparables (backlog §3.2, doc §8).

Selecciona el grupo de comparación más específico disponible usando
los 3 campos de contexto: facility_size, region, dc_type.

Jerarquía de fallback (del más al menos específico):
  1. region + facility_size + dc_type
  2. facility_size + dc_type
  3. dc_type
  4. global

En cada nivel se verifica si hay suficientes registros en dimension_scores
(mínimo MIN_GROUP_SIZE). Si no alcanza, sube al siguiente nivel.

Nota: en el MVP el motor siempre devuelve el grupo y su tamaño.
La distribución combinada la construye RebalanceEngine leyendo desde DB.
"""
from __future__ import annotations

from dataclasses import dataclass

MIN_GROUP_SIZE = 10   # mínimo de registros para usar un grupo


@dataclass
class PeerGroupResult:
    grupo_id: str          # identificador del grupo seleccionado
    nivel: int             # 1=más específico, 4=global
    descripcion: str       # texto legible del grupo
    n: int                 # tamaño del grupo en el dataset


class PeerGroupEngine:
    """
    Selecciona el grupo comparable y reporta su tamaño.
    Recibe session de DB para consultar dimension_scores.
    Sin FastAPI, sin cálculos estadísticos.
    """

    def seleccionar(
        self,
        facility_size: str | None,
        region: str | None,
        dc_type: str | None,
        session,
    ) -> PeerGroupResult:
        from app.models.tables import DimensionScore, DimensionEnum, Operator, SourceEnum
        from sqlalchemy import func

        def _contar(filtros: dict) -> int:
            q = session.query(func.count(Operator.id)).filter(
                Operator.source == SourceEnum.public_synthetic
            )
            if "region" in filtros and filtros["region"]:
                q = q.filter(Operator.region == filtros["region"])
            if "facility_size" in filtros and filtros["facility_size"]:
                q = q.filter(Operator.facility_size == filtros["facility_size"])
            if "dc_type" in filtros and filtros["dc_type"]:
                q = q.filter(Operator.dc_type == filtros["dc_type"])
            return q.scalar() or 0

        # Nivel 1: región + tamaño + tipo
        if facility_size and region and dc_type:
            n = _contar({"region": region, "facility_size": facility_size, "dc_type": dc_type})
            if n >= MIN_GROUP_SIZE:
                return PeerGroupResult(
                    grupo_id=f"{region}|{facility_size}|{dc_type}",
                    nivel=1,
                    descripcion=f"{dc_type} · {facility_size} · {region}",
                    n=n,
                )

        # Nivel 2: tamaño + tipo
        if facility_size and dc_type:
            n = _contar({"facility_size": facility_size, "dc_type": dc_type})
            if n >= MIN_GROUP_SIZE:
                return PeerGroupResult(
                    grupo_id=f"{facility_size}|{dc_type}",
                    nivel=2,
                    descripcion=f"{dc_type} · {facility_size}",
                    n=n,
                )

        # Nivel 3: solo tipo
        if dc_type:
            n = _contar({"dc_type": dc_type})
            if n >= MIN_GROUP_SIZE:
                return PeerGroupResult(
                    grupo_id=f"{dc_type}",
                    nivel=3,
                    descripcion=f"{dc_type}",
                    n=n,
                )

        # Nivel 4: global
        n = _contar({})
        return PeerGroupResult(
            grupo_id="global",
            nivel=4,
            descripcion="global",
            n=n,
        )
