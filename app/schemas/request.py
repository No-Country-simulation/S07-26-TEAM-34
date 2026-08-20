"""
Schemas de entrada — payload que envía el formulario a la API.
Los Literal values coinciden exactamente con los 'value' de config/questionnaire.yaml.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# ── Contexto (doc §8) ─────────────────────────────────────────────────────────

# ── Contexto del operador (doc §8) ────────────────────────────────────────────

FacilitySize = Literal["<1MW", "1-5MW", "5-20MW", ">20MW"]
DcType = Literal["hyperscale", "colocation", "enterprise", "edge"]
# Cerrado — mismos 5 valores de la calibración del dataset público (doc §8).
# Antes era texto libre; el match exacto de region en PeerGroupEngine
# nunca funcionaba porque cada operador lo tipeaba distinto.
Region = Literal["Norteamerica", "Latinoamerica", "Europa", "Asia-Pacifico", "Medio Oriente/Africa"]


class ContextoOperador(BaseModel):
    facility_size: FacilitySize
    region: Region
    dc_type: DcType


# ── Latencia (doc §3) ─────────────────────────────────────────────────────────

AutomatizacionLatencia = Literal[
    "automatizado",
    "alertas_manual",
    "reporte_periodico",
    "sin_proceso",
]


class RespuestasLatencia(BaseModel):
    p1_minutos: Annotated[float, Field(ge=0)]
    p2_minutos: Annotated[float, Field(ge=0)]
    p3: AutomatizacionLatencia


# ── Visibilidad (doc §4) ──────────────────────────────────────────────────────

FrecuenciaConsolidacion = Literal[
    "tiempo_real", "diario", "semanal", "mensual_o_mas", "nunca"
]
AccesoVista = Literal["cualquiera", "un_rol", "nadie"]


class RespuestasVisibilidad(BaseModel):
    p1_sistemas: Annotated[int, Field(ge=0)]
    p2: FrecuenciaConsolidacion
    p3: AccesoVista


# ── Atribución (doc §5) ───────────────────────────────────────────────────────

InterfazFriccion = Literal[
    "energia_cooling", "cooling_workload", "workload_energia", "no_sabria_decir"
]
RespalnoAtribucion = Literal["con_medicion", "estimacion", "sin_evidencia"]
VigenciaAtribucion = Literal["revision_activa", "revision_periodica", "nunca_revisada"]


class RespuestasAtribucion(BaseModel):
    p1: InterfazFriccion
    p2: RespalnoAtribucion
    p3: VigenciaAtribucion


# ── Auto-cuantificación (doc §6) ──────────────────────────────────────────────

UnidadCapacidad = Literal["mw", "kw"]
FrecuenciaRemedicion = Literal[
    "continuamente", "trimestral_semestral", "anual", "nunca_remedido"
]


class RespuestasAutoCuantificacion(BaseModel):
    p1_capacidad_total: Annotated[float | None, Field(default=None, ge=0)]
    p2_capacidad_utilizable: Annotated[float | None, Field(default=None, ge=0)]
    unidad: UnidadCapacidad
    p3: FrecuenciaRemedicion

    @model_validator(mode="after")
    def validar_coherencia_p1_p2(self) -> "RespuestasAutoCuantificacion":
        p1, p2 = self.p1_capacidad_total, self.p2_capacidad_utilizable
        if p1 is not None and p2 is not None and p2 > p1:
            raise ValueError(
                f"La capacidad utilizable ({p2}) no puede ser mayor "
                f"que la capacidad total instalada ({p1})."
            )
        return self


# ── Bloqueantes (doc §7) ──────────────────────────────────────────────────────

BloqueanteTipo = Literal[
    "presupuesto", "autoridad_politica", "herramientas", "personal", "nada"
]
SeveridadBloqueante = Literal[
    "no_es_real", "moderado", "fuerte", "estructural"
]


class RespuestasBloqueantes(BaseModel):
    p1_bloqueantes: list[BloqueanteTipo] = Field(min_length=1)
    p2_severidad: SeveridadBloqueante | None = None

    @model_validator(mode="after")
    def caso_borde_nada(self) -> "RespuestasBloqueantes":
        if self.p1_bloqueantes == ["nada"] and self.p2_severidad is None:
            return self
        if self.p2_severidad is None:
            raise ValueError("p2_severidad es obligatorio cuando hay bloqueantes distintos de 'nada'.")
        return self

    @field_validator("p1_bloqueantes")
    @classmethod
    def no_mezclar_nada(cls, v: list[BloqueanteTipo]) -> list[BloqueanteTipo]:
        if "nada" in v and len(v) > 1:
            raise ValueError("'nada' no puede combinarse con otros bloqueantes.")
        return v


# ── Payload completo ──────────────────────────────────────────────────────────

class CuestionarioRequest(BaseModel):
    contexto: ContextoOperador
    latencia: RespuestasLatencia
    visibilidad: RespuestasVisibilidad
    atribucion_friccion: RespuestasAtribucion
    auto_cuantificacion: RespuestasAutoCuantificacion
    bloqueantes: RespuestasBloqueantes
