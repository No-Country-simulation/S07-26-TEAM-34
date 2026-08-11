"""
Schemas de entrada — payload que envía el formulario a la API.

Cada campo se valida contra config/dimensiones.yaml.
Las opciones categóricas coinciden exactamente con los IDs del YAML.
Los inputs numéricos validan rangos mínimos.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Contexto del operador (doc §8) ────────────────────────────────────────────

FacilitySize = Literal["<1MW", "1-5MW", "5-20MW", ">20MW"]
DcType = Literal["hyperscale", "colocation", "enterprise", "edge"]


class ContextoOperador(BaseModel):
    facility_size: FacilitySize
    region: Annotated[str, Field(description="Continente o región amplia, no país exacto")]
    dc_type: DcType


# ── Latencia (doc §3) ─────────────────────────────────────────────────────────

AutomatizacionLatencia = Literal[
    "automatizado",
    "alertas_manual",
    "reporte_periodico",
    "sin_proceso",
]


class RespuestasLatencia(BaseModel):
    p1_minutos: Annotated[float, Field(ge=0, description="Minutos de ajuste de cooling")]
    p2_minutos: Annotated[float, Field(ge=0, description="Minutos de ajuste de energía")]
    p3: AutomatizacionLatencia


# ── Visibilidad (doc §4) ──────────────────────────────────────────────────────

FrecuenciaConsolidacion = Literal[
    "tiempo_real", "diario", "semanal", "mensual_o_mas", "nunca"
]
AccesoVista = Literal["cualquiera", "un_rol", "nadie"]


class RespuestasVisibilidad(BaseModel):
    p1_sistemas: Annotated[
        int, Field(ge=0, description="Cantidad de sistemas de monitoreo")
    ]
    p2: FrecuenciaConsolidacion
    p3: AccesoVista


# ── Atribución de fricción (doc §5) ──────────────────────────────────────────

InterfazFriccion = Literal[
    "energia_cooling", "cooling_workload", "workload_energia", "no_sabria_decir"
]
RespalnoAtribucion = Literal["con_medicion", "estimacion", "sin_evidencia"]
VigenciaAtribucion = Literal["revision_activa", "revision_periodica", "nunca_revisada"]


class RespuestasAtribucion(BaseModel):
    p1: InterfazFriccion                    # nominal — no entra al score
    p2: RespalnoAtribucion
    p3: VigenciaAtribucion

    @model_validator(mode="after")
    def caso_borde_no_sabria(self) -> "RespuestasAtribucion":
        """Si p1 = 'no_sabria', p2 y p3 se fuerzan a 0 en el scoring engine.
        Aquí solo documentamos que los valores enviados se aceptan igualmente."""
        return self


# ── Auto-cuantificación (doc §6) ──────────────────────────────────────────────

UnidadCapacidad = Literal["mw", "kw"]
FrecuenciaRemedicion = Literal[
    "continuamente", "trimestral_semestral", "anual", "nunca_remedido"
]


class RespuestasAutoCuantificacion(BaseModel):
    p1_capacidad_total: Annotated[
        float | None,
        Field(default=None, ge=0, description="Capacidad instalada total")
    ]
    p2_capacidad_utilizable: Annotated[
        float | None,
        Field(default=None, ge=0, description="Capacidad máxima usable hoy")
    ]
    unidad: UnidadCapacidad
    p3: FrecuenciaRemedicion

    @model_validator(mode="after")
    def validar_coherencia_p1_p2(self) -> "RespuestasAutoCuantificacion":
        """
        Validación inline (doc §6): si se proveen ambos valores,
        P2 debe ser <= P1. Si no se cumple, los valores se marcan como
        incoherentes (el scoring engine los tratará como score_completitud=0).
        """
        p1 = self.p1_capacidad_total
        p2 = self.p2_capacidad_utilizable
        if p1 is not None and p2 is not None:
            if p2 > p1:
                raise ValueError(
                    f"La capacidad utilizable ({p2}) no puede ser mayor "
                    f"que la capacidad total instalada ({p1}). "
                    "Verificar los valores ingresados."
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
    p1_bloqueantes: list[BloqueanteTipo] = Field(
        min_length=1,
        description="Al menos una opción debe seleccionarse",
    )
    p2_severidad: SeveridadBloqueante | None = None

    @model_validator(mode="after")
    def caso_borde_nada(self) -> "RespuestasBloqueantes":
        """
        Caso borde (doc §7): si solo se elige 'nada', p2 se autoasigna 100
        (no se le pregunta al usuario — el engine lo maneja).
        """
        if self.p1_bloqueantes == ["nada"] and self.p2_severidad is None:
            # Aceptar: el engine asignará p2 = 100 automáticamente
            return self
        if self.p2_severidad is None:
            raise ValueError(
                "Se requiere indicar la severidad del bloqueante (p2_severidad) "
                "cuando se selecciona al menos un bloqueante distinto de 'nada'."
            )
        return self

    @field_validator("p1_bloqueantes")
    @classmethod
    def no_mezclar_nada_con_otros(cls, v: list[BloqueanteTipo]) -> list[BloqueanteTipo]:
        """'nada' no puede combinarse con otros bloqueantes."""
        if "nada" in v and len(v) > 1:
            raise ValueError(
                "'nada' no puede seleccionarse junto con otros bloqueantes."
            )
        return v


# ── Payload completo del cuestionario ────────────────────────────────────────

class CuestionarioRequest(BaseModel):
    """
    Payload completo que envía el formulario a POST /respuestas.
    Incluye los 3 campos de contexto y las 5 dimensiones.
    """
    contexto: ContextoOperador
    latencia: RespuestasLatencia
    visibilidad: RespuestasVisibilidad
    atribucion_friccion: RespuestasAtribucion
    auto_cuantificacion: RespuestasAutoCuantificacion
    bloqueantes: RespuestasBloqueantes
