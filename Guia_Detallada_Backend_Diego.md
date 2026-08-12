# Guía detallada — réplica de las correcciones de backend

*Documento interno, no se commitea al repo. Contiene el contenido completo y exacto de cada archivo tocado en la rama `correcciones-criticas`, para que se pueda reescribir/aplicar manualmente sobre `develop`. No incluye nada de `frontend/` — eso se sube aparte.*

Convención: cuando dice "reemplazar el archivo completo por esto", es el contenido final entero del archivo, no un fragmento. Cuando dice "cambiar esta línea por esta otra", es una edición puntual.

---

## 0. Paso previo — eliminar el árbol legacy

Estos archivos y carpetas existen en `develop` y no deberían — son de una implementación paralela (Kiro) que quedó mezclada con el código real en `app/`. Borrar exactamente esta lista (nada más, nada menos):

```
.kiro/specs/benchmark-core/design.md
.kiro/specs/benchmark-core/requirements.md
.kiro/specs/benchmark-core/tasks.md
.kiro/steering/core-rules.md
.kiro/steering/privacy.md
.kiro/steering/rebalancing.md
AGENTS.md
Arquitectura_Benchmark_Data_Centers_Kiro.docx
Guia_PRs_Migracion.md
README_KIRO.md
alembic.ini
alembic/README
alembic/env.py
alembic/script.py.mako
alembic/versions/ee400488cb93_initial_schema.py
config/dimensiones.yaml
config/methodology/1.0.0/cohorts.yaml
config/methodology/1.0.0/privacy.yaml
config/methodology/1.0.0/questionnaire.yaml
config/methodology/v1.0.0/cohorts.yaml
config/methodology/v1.0.0/privacy.yaml
config/methodology/v1.0.0/questionnaire.yaml
docs/00_PROJECT_CHARTER.md
docs/01_SYSTEM_ARCHITECTURE.md
docs/02_BENCHMARK_METHODOLOGY.md
docs/03_DYNAMIC_REBALANCING.md
docs/04_DATA_PRIVACY_AND_AGGREGATION.md
docs/05_API_AND_OUTPUT_CONTRACTS.md
docs/06_TESTING_AND_BACKTESTING.md
docs/07_IMPLEMENTATION_ROADMAP.md
docs/08_RISKS_AND_OPEN_DECISIONS.md
docs/99_SOURCES.md
docs/adr/ADR-001-modular-monolith-and-engine-boundaries.md
docs/adr/ADR-002-immutable-benchmark-snapshots.md
docs/adr/ADR-003-validation-as-ingestion-gate.md
docs/adr/ADR-004-privacy-and-aggregation-boundary.md
docs/adr/ADR-005-dynamic-rebalancing-per-dimension-and-cohort.md
docs/adr/ADR-006-hierarchical-cohort-fallback.md
docs/adr/ADR-007-no-composite-score-in-mvp.md
docs/adr/ADR-008-llm-outside-the-statistical-path.md
docs/adr/ADR-009-versioned-declarative-methodology.md
docs/adr/ADR-010-online-offline-processing-split.md
docs/arquitectura_objetivo.md
main.py                    (se recrea en app/main.py, ver sección 8)
src/benchmark/__init__.py
src/benchmark/api/__init__.py
src/benchmark/api/admin_routes.py
src/benchmark/api/app.py
src/benchmark/api/routes.py
src/benchmark/api/schemas.py
src/benchmark/application/__init__.py
src/benchmark/application/process_response.py
src/benchmark/config/__init__.py
src/benchmark/config/loader.py
src/benchmark/db/__init__.py
src/benchmark/db/base.py
src/benchmark/db/models.py
src/benchmark/db/repository.py
src/benchmark/db/seed.py
src/benchmark/domain/__init__.py
src/benchmark/domain/models.py
src/benchmark/engines/__init__.py
src/benchmark/engines/benchmark.py
src/benchmark/engines/cohort.py
src/benchmark/engines/interpretation.py
src/benchmark/engines/llm_interpretation.py
src/benchmark/engines/rebalancing.py
src/benchmark/engines/scoring.py
src/benchmark/engines/snapshot_builder.py
src/benchmark/engines/top_quartile.py
src/benchmark/engines/validation.py
src/benchmark/jobs/__init__.py
src/benchmark/jobs/build_snapshot.py
src/benchmark/jobs/methodology_update.py
src/benchmark/monitoring/__init__.py
src/benchmark/monitoring/dashboard.py
src/benchmark/monitoring/drift_monitor.py
tests/fixtures.py
tests/test_integration.py
tests/test_offline_job.py
tests/test_persistence.py
tests/test_phase6.py
tests/test_rebalancing.py
tests/test_scoring.py
tests/test_validation.py
```

Después de borrar todo esto, quedan las carpetas `.kiro/`, `alembic/`, `src/` y `docs/adr/` vacías — borrarlas también (`docs/` en sí queda, porque tiene `Backlog_Definitivo_v3.md` y `Documento_Metodologico_Benchmark.md`, esos NO se tocan).

---

## 1. `app/config/loader.py` — reemplazar el archivo completo

**Por qué**: leía `config/dimensiones.yaml` (un archivo con estructura propia, generado aparte) en vez de `config/questionnaire.yaml` (el canónico, fuente de verdad real). Reescrito para parsear `questionnaire.yaml` manteniendo exactamente la misma API pública que ya usa `scoring_engine.py` — no hace falta tocar `scoring_engine.py` por este cambio salvo el punto 3 de más abajo.

Contenido completo nuevo:

```python
"""
Loader de config/questionnaire.yaml — fuente única de preguntas, opciones y scores.

Regla: ninguna pregunta, opción ni score se escribe a mano en un .py.
Todo sale de aquí.

Uso:
    from app.config.loader import get_config
    cfg = get_config()
    score = cfg.score_categoria("latencia", "p3", "automatizado")  # → 100
    score = cfg.score_numerico("latencia", "p1", 8.0)              # → 75
"""
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

import yaml

# Mapea los ids largos de config/questionnaire.yaml a los ids cortos
# que usan scoring_engine.py y rebalance_engine.py.
_DIMENSION_ID_MAP: dict[str, str] = {
    "latencia_coordinacion": "latencia",
    "visibilidad_cross_layer": "visibilidad",
    "atribucion_friccion": "atribucion_friccion",
    "auto_cuantificacion": "auto_cuantificacion",
    "bloqueantes": "bloqueantes",
}

# Score por cantidad de bloqueantes marcados (doc §7, derived.cantidad_p1_score).
_SCORE_CANTIDAD_BLOQUEANTES_DEFAULT: dict[str, int] = {
    "0": 100, "1": 67, "2": 33, "3_o_mas": 0,
}

_PREGUNTA_ID_RE = re.compile(r"(?:^|_)(p\d+)(?:_|$)")


def _resolve_config_path() -> Path:
    """Resuelve la ruta al YAML en runtime (no en import time)."""
    env = os.environ.get("QUESTIONNAIRE_YAML", "")
    if env:
        return Path(env)
    return Path(__file__).parent.parent.parent / "config" / "questionnaire.yaml"


def _short_pregunta_id(full_id: str) -> str:
    """Extrae 'p1'/'p2'/'p3' del id largo (ej. 'lat_p1_minutos_cooling' → 'p1')."""
    match = _PREGUNTA_ID_RE.search(full_id)
    if not match:
        raise ValueError(f"No se pudo extraer el id corto de pregunta de '{full_id}'")
    return match.group(1)


# ── Clases de configuración ───────────────────────────────────────────────────

class BucketScore:
    """Un bucket de normalización para variables numéricas (doc §3, P1/P2 de Latencia)."""

    def __init__(self, max_val: float | None, score: int) -> None:
        self.max_val = max_val   # None = sin límite superior
        self.score = score

    def matches(self, value: float) -> bool:
        if self.max_val is None:
            return True
        return value <= self.max_val


class PreguntaConfig:
    def __init__(self, pregunta_id: str, data: dict) -> None:
        self.id = pregunta_id
        self.tipo: str = data["type"]
        self.texto: str = data.get("prompt", "")

        # Opciones categóricas → {id: score}
        self._opciones: dict[str, int] = {}
        for opt in data.get("options", []):
            if "score" in opt:
                self._opciones[opt["value"]] = opt["score"]

        # Buckets para variables numéricas
        scoring = data.get("scoring", {})
        self._buckets: list[BucketScore] = [
            BucketScore(b.get("max_inclusive"), b["score"])
            for b in scoring.get("buckets", [])
        ]

        # Score por cantidad de bloqueantes (solo dimensión bloqueantes P1)
        self._score_por_cantidad: dict[str, int] = _SCORE_CANTIDAD_BLOQUEANTES_DEFAULT

        # ¿Es nominal? (no entra al índice)
        self.es_nominal: bool = self.tipo in (
            "categorical_nominal",
            "categorical_nominal_multiselect",
        )

        # ¿Es input numérico?
        self.es_numerico: bool = self.tipo == "numeric"

    def score_categoria(self, opcion_id: str) -> int:
        """Score para una respuesta categórica ordinal."""
        if opcion_id not in self._opciones:
            raise KeyError(
                f"Opción '{opcion_id}' no existe en pregunta '{self.id}'. "
                f"Opciones válidas: {list(self._opciones.keys())}"
            )
        return self._opciones[opcion_id]

    def score_numerico(self, valor: float) -> int:
        """Score para una variable numérica usando los buckets del YAML."""
        if not self._buckets:
            raise ValueError(f"Pregunta '{self.id}' no tiene buckets definidos")
        for bucket in self._buckets:
            if bucket.matches(valor):
                return bucket.score
        return 0

    def score_cantidad_bloqueantes(self, cantidad: int) -> int:
        """Score para P1 de Bloqueantes según la cantidad marcada."""
        if cantidad == 0:
            return self._score_por_cantidad.get("0", 100)
        if cantidad == 1:
            return self._score_por_cantidad.get("1", 67)
        if cantidad == 2:
            return self._score_por_cantidad.get("2", 33)
        return self._score_por_cantidad.get("3_o_mas", 0)

    def opciones_ids(self) -> list[str]:
        return list(self._opciones.keys())


class DimensionConfig:
    def __init__(self, dim_id: str, data: dict) -> None:
        self.id = dim_id
        self.label: str = data["label"]
        self.descripcion: str = data.get("note", "")
        self.formula: str = data.get("index_formula", "")
        self.preguntas: dict[str, PreguntaConfig] = {}
        for qdata in data["questions"]:
            short_id = _short_pregunta_id(qdata["id"])
            self.preguntas[short_id] = PreguntaConfig(short_id, qdata)

    def pregunta(self, pid: str) -> PreguntaConfig:
        if pid not in self.preguntas:
            raise KeyError(f"Pregunta '{pid}' no existe en dimensión '{self.id}'")
        return self.preguntas[pid]


class SegmentacionConfig:
    def __init__(self, data: list[dict]) -> None:
        self._campos: dict[str, list[str]] = {
            campo["id"]: campo.get("options", [])
            for campo in data
        }

    def opciones(self, campo: str) -> list[str]:
        return self._campos.get(campo, [])

    def total_categorias(self) -> int:
        """Total de combinaciones posibles (para factor_diversidad del rebalanceo)."""
        total = 1
        for opts in self._campos.values():
            if opts:
                total *= len(opts)
        return total


class DimensionesConfig:
    """
    Acceso tipado a config/questionnaire.yaml.
    Cacheada — se carga una sola vez por proceso.
    """

    def __init__(self, data: dict) -> None:
        self.version: str = data["version"]
        self.segmentacion = SegmentacionConfig(data["segmentation_fields"])
        self.dimensiones: dict[str, DimensionConfig] = {
            _DIMENSION_ID_MAP[did]: DimensionConfig(_DIMENSION_ID_MAP[did], ddata)
            for did, ddata in data["dimensions"].items()
        }

    def dimension(self, dim_id: str) -> DimensionConfig:
        if dim_id not in self.dimensiones:
            raise KeyError(
                f"Dimensión '{dim_id}' no existe. "
                f"Dimensiones válidas: {list(self.dimensiones.keys())}"
            )
        return self.dimensiones[dim_id]

    def score_categoria(self, dim_id: str, pregunta_id: str, opcion_id: str) -> int:
        return self.dimension(dim_id).pregunta(pregunta_id).score_categoria(opcion_id)

    def score_numerico(self, dim_id: str, pregunta_id: str, valor: float) -> int:
        return self.dimension(dim_id).pregunta(pregunta_id).score_numerico(valor)


# ── Punto de entrada cacheado ─────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_config() -> DimensionesConfig:
    """Carga y cachea config/questionnaire.yaml. Falla rápido si el archivo no existe."""
    path = _resolve_config_path()
    if not path.exists():
        raise FileNotFoundError(
            f"No se encontró config/questionnaire.yaml en {path}. "
            "Verificar la variable de entorno QUESTIONNAIRE_YAML o la estructura del proyecto."
        )
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return DimensionesConfig(data)
```

Notar el mapeo de ids largos → cortos (`_DIMENSION_ID_MAP`, línea ~24) y la extracción mecánica de `p1`/`p2`/`p3` desde el id largo de cada pregunta vía regex (`_short_pregunta_id`) — así el resto del código sigue usando los ids cortos que ya tenía, sin tocar `scoring_engine.py` ni `rebalance_engine.py` en su lógica interna.

**Nota sobre la variable de entorno**: antes se llamaba `DIMENSIONES_YAML`, ahora es `QUESTIONNAIRE_YAML` — si hay algún script o config que la use, actualizar el nombre.

---

## 2. `app/schemas/request.py` — valores `Literal` a corregir

**Por qué**: varios valores no coincidían con las opciones reales de `config/questionnaire.yaml` — cualquier request válida desde un frontend real habría fallado la validación de Pydantic contra este schema.

Cambios exactos, línea por línea (buscar y reemplazar cada bloque):

**Contexto** — antes:
```python
FacilitySize = Literal["menos_1mw", "1_5mw", "5_20mw", "mas_20mw"]
Region = Literal["latam", "norteamerica", "europa", "apac", "otro"]
DcType = Literal["hyperscale", "colocation", "enterprise", "edge"]


class ContextoOperador(BaseModel):
    facility_size: FacilitySize
    region: Region
    dc_type: DcType
```
Después:
```python
FacilitySize = Literal["<1MW", "1-5MW", "5-20MW", ">20MW"]
DcType = Literal["hyperscale", "colocation", "enterprise", "edge"]


class ContextoOperador(BaseModel):
    facility_size: FacilitySize
    region: Annotated[str, Field(description="Continente o región amplia, no país exacto")]
    dc_type: DcType
```
(`region` deja de ser un `Literal` cerrado — es texto libre según el documento metodológico §8, "continente o región amplia, no país exacto, para no comprometer el anonimato").

**Latencia P3** — antes:
```python
AutomatizacionLatencia = Literal[
    "automatizado",
    "alertas_accion_manual",
    "reporte_revision_manual",
    "sin_proceso",
]
```
Después:
```python
AutomatizacionLatencia = Literal[
    "automatizado",
    "alertas_manual",
    "reporte_periodico",
    "sin_proceso",
]
```

**Visibilidad P2/P3** — antes:
```python
FrecuenciaConsolidacion = Literal[
    "tiempo_real", "diario", "semanal", "mensual", "nunca"
]
AccesoVista = Literal["cualquier_responsable", "rol_especifico", "nadie"]
```
Después:
```python
FrecuenciaConsolidacion = Literal[
    "tiempo_real", "diario", "semanal", "mensual_o_mas", "nunca"
]
AccesoVista = Literal["cualquiera", "un_rol", "nadie"]
```

**Atribución P1/P2/P3** — antes:
```python
InterfazFriccion = Literal[
    "energia_cooling", "cooling_workload", "workload_energia", "no_sabria"
]
RespalnoAtribucion = Literal["con_evidencia", "estimacion", "sin_evidencia"]
VigenciaAtribucion = Literal["activamente", "periodicamente", "nunca"]
```
Después:
```python
InterfazFriccion = Literal[
    "energia_cooling", "cooling_workload", "workload_energia", "no_sabria_decir"
]
RespalnoAtribucion = Literal["con_medicion", "estimacion", "sin_evidencia"]
VigenciaAtribucion = Literal["revision_activa", "revision_periodica", "nunca_revisada"]
```

**Auto-cuantificación P3** — antes:
```python
UnidadCapacidad = Literal["mw", "kw"]
FrecuenciaRemedicion = Literal[
    "tiempo_real", "trimestral_semestral", "anual", "nunca"
]
```
Después:
```python
UnidadCapacidad = Literal["mw", "kw"]
FrecuenciaRemedicion = Literal[
    "continuamente", "trimestral_semestral", "anual", "nunca_remedido"
]
```

**Bloqueantes P2** — antes:
```python
SeveridadBloqueante = Literal[
    "no_bloqueante", "moderado", "fuerte", "estructural"
]
```
Después:
```python
SeveridadBloqueante = Literal[
    "no_es_real", "moderado", "fuerte", "estructural"
]
```

**Bloqueantes P1** (`presupuesto`, `autoridad_politica`, `herramientas`, `personal`, `nada`) — este no cambia, ya estaba correcto.

Contenido completo final del archivo (para copiar/pegar entero en vez de aplicar los diffs de a uno):

```python
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
```

---

## 3. `app/engines/scoring_engine.py` — un cambio puntual

**Por qué**: consecuencia directa del punto 2 — el valor `"no_sabria"` de Atribución P1 pasó a llamarse `"no_sabria_decir"`, y el caso borde que lo chequea seguía comparando contra el valor viejo (nunca se iba a disparar).

Buscar (dentro de `_score_atribucion`):
```python
        # Caso borde (doc §5): si P1 = "no_sabria", P2 y P3 → 0
        if atr.p1 == "no_sabria":
            sp2 = sp3 = 0
            notas.append("P1='no_sabria': P2 y P3 se asignaron 0 automáticamente")
```
Reemplazar por:
```python
        # Caso borde (doc §5): si P1 = "no_sabria_decir", P2 y P3 → 0
        if atr.p1 == "no_sabria_decir":
            sp2 = sp3 = 0
            notas.append("P1='no_sabria_decir': P2 y P3 se asignaron 0 automáticamente")
```
Ningún otro cambio en este archivo.

---

## 4. `config/seed_public_dataset.py` — reemplazar el archivo completo

**Por qué**: generaba un CSV nuevo con `Faker` en cada corrida, pisando el dataset de 1000 filas calibrado contra fuentes públicas reales de la industria (Uptime Institute, Gartner). Además esa versión importaba `from faker import Faker`, una dependencia que ni siquiera estaba declarada en `pyproject.toml` — habría roto en cualquier entorno limpio.

**Importante**: el CSV real (`config/dataset_publico_sintetico.csv`) usa **labels en español, no los value-ids del schema** (ej. la columna `lat_p3_automatizacion` trae el texto `"Automatizado, sin intervencion humana"`, no `"automatizado"`), y ya trae los scores por dimensión **precalculados** en columnas `*_score`. Por eso el nuevo script NO reconstruye un `CuestionarioRequest` ni corre el `ScoringEngine` sobre cada fila — carga los scores tal cual vienen del CSV. Si el CSV no está en el repo o se corrompió, hay que recuperarlo de `main` (`git show main:config/dataset_publico_sintetico.csv`) o de la rama `correcciones-criticas`.

Contenido completo nuevo:

```python
"""
Seed del dataset público sintético (PR 1 — backlog §11).

Carga config/dataset_publico_sintetico.csv (1000 filas, calibradas contra
fuentes públicas de la industria — Uptime Institute, Gartner, entre otros)
en las tablas operators y dimension_scores con source="public_synthetic".

El CSV ya trae los scores por dimensión precalculados durante la calibración
(columnas *_score) — este script NO regenera datos ni recalcula scores,
solo los persiste tal cual.

Uso:
    python -m config.seed_public_dataset [--force]
    o desde la raíz:
    python config/seed_public_dataset.py [--force]
"""
from __future__ import annotations

import argparse
import csv
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Añadir el directorio raíz al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.loader import get_config
from app.models.database import Base, get_engine, get_session
from app.models.tables import DimensionEnum, DimensionScore, Operator, SourceEnum

DATASET_CSV_PATH = Path(__file__).parent / "dataset_publico_sintetico.csv"


def _fila_a_raw_answers(fila: dict, campos: list[str]) -> dict:
    return {campo: fila[campo] for campo in campos if fila.get(campo) not in (None, "")}


def cargar_csv_en_bd(csv_path: Path, force: bool = False) -> int:
    """
    Lee el CSV calibrado y carga las filas en operators + dimension_scores.
    Si ya hay datos con source="public_synthetic" y force=False, no los duplica.
    Retorna el número de registros cargados.
    """
    Base.metadata.create_all(get_engine())
    cfg = get_config()

    with open(csv_path, encoding="utf-8") as f:
        filas = list(csv.DictReader(f))

    with get_session() as session:
        existentes = session.query(Operator).filter_by(source=SourceEnum.public_synthetic).count()
        if existentes > 0 and not force:
            print(f"Ya existen {existentes} registros con source='public_synthetic'")
            print("Usa --force para sobrescribir")
            return existentes

        if force and existentes > 0:
            print(f"Eliminando {existentes} registros existentes...")
            session.query(Operator).filter_by(source=SourceEnum.public_synthetic).delete()
            session.commit()

        print(f"Cargando {len(filas)} registros en la base de datos...")
        cargados = 0

        for fila in filas:
            operator_id = fila.get("operator_id") or str(uuid.uuid4())

            session.add(Operator(
                id=operator_id,
                source=SourceEnum.public_synthetic,
                region=fila["region"],
                facility_size=fila["tamano_facility"],
                dc_type=fila["tipo_data_center"].lower(),
                benchmark_version=cfg.version,
                dimension_version=cfg.version,
                created_at=datetime.now(timezone.utc),
            ))

            session.add(DimensionScore(
                operator_id=operator_id,
                dimension=DimensionEnum.latencia,
                score=float(fila["lat_score"]),
                raw_answers=_fila_a_raw_answers(
                    fila, ["lat_p1_minutos_cooling", "lat_p2_minutos_energia", "lat_p3_automatizacion"]
                ),
            ))
            session.add(DimensionScore(
                operator_id=operator_id,
                dimension=DimensionEnum.visibilidad,
                score=float(fila["vis_score"]),
                raw_answers=_fila_a_raw_answers(
                    fila, ["vis_p1_cantidad_sistemas", "vis_p2_frecuencia_consolidacion", "vis_p3_acceso_vista_unificada"]
                ),
            ))
            session.add(DimensionScore(
                operator_id=operator_id,
                dimension=DimensionEnum.atribucion_friccion,
                score=float(fila["atr_score"]),
                raw_answers=_fila_a_raw_answers(
                    fila, ["atr_p1_interfaz", "atr_p2_respaldo", "atr_p3_vigencia"]
                ),
            ))
            session.add(DimensionScore(
                operator_id=operator_id,
                dimension=DimensionEnum.auto_cuantificacion,
                score=float(fila["auto_score"]),
                raw_answers=_fila_a_raw_answers(
                    fila,
                    [
                        "auto_p1_capacidad_instalada_mw",
                        "auto_p2_capacidad_utilizable_mw",
                        "auto_pct_varada_calculado",
                        "auto_p3_frecuencia_remedicion",
                    ],
                ),
            ))
            session.add(DimensionScore(
                operator_id=operator_id,
                dimension=DimensionEnum.bloqueantes,
                score=float(fila["blk_score"]),
                raw_answers=_fila_a_raw_answers(
                    fila, ["blk_p1_seleccionados", "blk_p1_cantidad", "blk_p2_severidad"]
                ),
            ))

            cargados += 1
            if cargados % 100 == 0:
                session.commit()
                print(f"  {cargados}/{len(filas)}...")

        session.commit()

    print(f"Total cargados: {cargados} registros")
    return cargados


def main():
    parser = argparse.ArgumentParser(description="Seed del dataset público sintético")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Sobrescribir datos existentes en BD",
    )
    args = parser.parse_args()

    if not DATASET_CSV_PATH.exists():
        raise FileNotFoundError(
            f"No se encontró {DATASET_CSV_PATH}. "
            "Este archivo debe existir versionado en el repo — no se genera en runtime."
        )

    cargar_csv_en_bd(DATASET_CSV_PATH, args.force)


if __name__ == "__main__":
    main()
```

Columnas exactas que tiene que tener el CSV para que este script funcione (header real de `config/dataset_publico_sintetico.csv`):
```
operator_id, region, tamano_facility, tipo_data_center,
lat_p1_minutos_cooling, lat_p2_minutos_energia, lat_p3_automatizacion, lat_score,
vis_p1_cantidad_sistemas, vis_p2_frecuencia_consolidacion, vis_p3_acceso_vista_unificada, vis_score,
atr_p1_interfaz, atr_p2_respaldo, atr_p3_vigencia, atr_score,
auto_p1_capacidad_instalada_mw, auto_p2_capacidad_utilizable_mw, auto_pct_varada_calculado, auto_p3_frecuencia_remedicion, auto_score,
blk_p1_seleccionados, blk_p1_cantidad, blk_p2_severidad, blk_score
```

---

## 5. `app/engines/rebalance_engine.py` — dos cambios puntuales

**Cambio 1** — agregar el import de `random` y la constante de seed, al principio del archivo:

Buscar:
```python
from dataclasses import dataclass, field

from app.config.loader import get_config

# Constante de suavizado — doc §9: con k=50, n=50 → peso≈50%; n=200 → peso≈80%
K: int = 50
```
Reemplazar por:
```python
import random
from dataclasses import dataclass, field

from app.config.loader import get_config

# Constante de suavizado — doc §9: con k=50, n=50 → peso≈50%; n=200 → peso≈80%
K: int = 50

# Seed fijo para que el muestreo de _mezclar() sea reproducible
# (mismos inputs → mismos percentiles, requerido para tests determinísticos).
_SEED: int = 42
```

**Cambio 2** — dentro del método estático `_mezclar()`, usar un `random.Random` con seed fijo en vez del módulo `random` global:

Buscar:
```python
        import math, random

        if not publicos and not primarios:
            return []

        n_total = max(len(publicos), 200)
        n_pub = math.ceil(n_total * w_pub)
        n_pri = math.ceil(n_total * w_pri)

        # Muestreo con reemplazo proporcional al peso
        muestra_pub = (
            random.choices(publicos, k=n_pub) if publicos and n_pub > 0 else []
        )
        muestra_pri = (
            random.choices(primarios, k=n_pri) if primarios and n_pri > 0 else []
        )
```
Reemplazar por:
```python
        import math

        if not publicos and not primarios:
            return []

        n_total = max(len(publicos), 200)
        n_pub = math.ceil(n_total * w_pub)
        n_pri = math.ceil(n_total * w_pri)

        # Muestreo con reemplazo proporcional al peso — seed fijo para reproducibilidad
        rng = random.Random(_SEED)
        muestra_pub = (
            rng.choices(publicos, k=n_pub) if publicos and n_pub > 0 else []
        )
        muestra_pri = (
            rng.choices(primarios, k=n_pri) if primarios and n_pri > 0 else []
        )
```
Nada más cambia en este archivo — la fórmula de `peso_primario`/`peso_publico`/`factor_diversidad` ya estaba bien.

---

## 6. `app/services/benchmark_service.py` — el bug más importante

**Por qué**: `scores_primarios` estaba hardcodeado en `[]` con el comentario `# dataset primario vacío al inicio`. Esto significa que, sin importar cuántas respuestas reales se acumularan en la base, el motor de rebalanceo **siempre** iba a recibir una lista vacía de scores primarios — el peso primario de la fórmula (doc §9) iba a quedar en 0 para siempre, no solo al principio. Faltaba la consulta real a `source=primary`.

**Cambio 1** — al principio del archivo, reemplazar la función `_cargar_dataset_publico()` completa por dos funciones nuevas:

Buscar:
```python
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
```
Reemplazar por:
```python
_DIMENSIONES = ["latencia", "visibilidad", "atribucion_friccion",
                "auto_cuantificacion", "bloqueantes"]


def _cargar_scores_por_source(source: "SourceEnum") -> dict[str, list[float]]:
    """Carga scores por dimensión desde dimension_scores, filtrando por source."""
    from app.models.tables import DimensionScore, Operator

    dataset: dict[str, list[float]] = {dim: [] for dim in _DIMENSIONES}

    with get_session() as session:
        filas = session.query(DimensionScore.score, DimensionScore.dimension)\
            .join(Operator, Operator.id == DimensionScore.operator_id)\
            .filter(Operator.source == source)\
            .all()

        for score, dimension in filas:
            if dimension.value in dataset:
                dataset[dimension.value].append(score)

    return dataset


def _contar_categorias_cubiertas_primarias() -> int:
    """
    Cuenta combinaciones distintas de (region, facility_size, dc_type)
    presentes entre los operadores con source=primary (doc §9, factor_diversidad).
    """
    from app.models.tables import Operator, SourceEnum

    with get_session() as session:
        combinaciones = session.query(
            Operator.region, Operator.facility_size, Operator.dc_type
        ).filter(Operator.source == SourceEnum.primary).distinct().all()

    return len(combinaciones)
```

**Cambio 2** — dentro de `procesar()`, reemplazar el bloque de carga de datos y el loop de rebalanceo:

Buscar:
```python
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
```
Reemplazar por:
```python
        # ── 4. Cargar datasets desde BD (PR 1) ────────────────────────────────
        from app.models.tables import SourceEnum
        dataset_publico = _cargar_scores_por_source(SourceEnum.public_synthetic)
        dataset_primario = _cargar_scores_por_source(SourceEnum.primary)
        categorias_cubiertas = _contar_categorias_cubiertas_primarias()

        # ── 5. Rebalanceo (motor 3.3) ─────────────────────────────────────────
        # Con n_valido=0 (sin respuestas primarias todavía) el motor devuelve
        # peso_primario=0 automáticamente (doc §9) — no hace falta un caso especial acá.
        rebalanceo_por_dim = {}
        distribuciones = {}
        for dim in scores:
            rb = self._rebalanceo.rebalancear(
                scores_publicos=dataset_publico.get(dim, []),
                scores_primarios=dataset_primario.get(dim, []),
                categorias_cubiertas=categorias_cubiertas,
            )
            rebalanceo_por_dim[dim] = rb
            distribuciones[dim] = rb.distribucion_combinada
```

**Cambio 3** (llega junto con el punto 9 de esta guía, LLM) — dentro de `procesar()`, la llamada a interpretar pasa a incluir `raw_answers` y `contexto`:

Buscar:
```python
        # ── 7. Interpretación (motor 3.6) ─────────────────────────────────────
        interp = self._interpretacion.interpretar(scores, benchmark_result, top_quartile_result)
```
Reemplazar por:
```python
        # ── 7. Interpretación (motor 3.6) ─────────────────────────────────────
        interp = self._interpretacion.interpretar(
            scores, benchmark_result, top_quartile_result,
            raw_answers=raw_answers, contexto=req.contexto.model_dump(),
        )
```

**Cambio 4** (llega junto con el punto 8, endpoints) — agregar un método nuevo `obtener_resultado()` a la clase `BenchmarkService`, antes del método `pdf_input` existente:

```python
    def obtener_resultado(self, operator_id: str) -> ResultadoResponse | None:
        """Lee un resultado ya calculado desde DB (no recalcula)."""
        with get_session() as session:
            result = self._repo.obtener_resultado(session, operator_id)
            if result is None:
                return None
            return ResultadoResponse(
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
```
(Nota: `score=0.0` es intencional — la tabla `results` solo guarda `percentiles`, no los scores crudos por dimensión, así que al leer desde DB no se puede reconstruir el score original sin recalcular. Es una limitación conocida, no un bug — si en algún momento hace falta el score real acá, hay que agregar una columna a la tabla `results` o guardar los scores en JSON ahí también.)

Contenido completo final del archivo, para pegar entero:

```python
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


_DIMENSIONES = ["latencia", "visibilidad", "atribucion_friccion",
                "auto_cuantificacion", "bloqueantes"]


def _cargar_scores_por_source(source: "SourceEnum") -> dict[str, list[float]]:
    """Carga scores por dimensión desde dimension_scores, filtrando por source."""
    from app.models.tables import DimensionScore, Operator

    dataset: dict[str, list[float]] = {dim: [] for dim in _DIMENSIONES}

    with get_session() as session:
        filas = session.query(DimensionScore.score, DimensionScore.dimension)\
            .join(Operator, Operator.id == DimensionScore.operator_id)\
            .filter(Operator.source == source)\
            .all()

        for score, dimension in filas:
            if dimension.value in dataset:
                dataset[dimension.value].append(score)

    return dataset


def _contar_categorias_cubiertas_primarias() -> int:
    """
    Cuenta combinaciones distintas de (region, facility_size, dc_type)
    presentes entre los operadores con source=primary (doc §9, factor_diversidad).
    """
    from app.models.tables import Operator, SourceEnum

    with get_session() as session:
        combinaciones = session.query(
            Operator.region, Operator.facility_size, Operator.dc_type
        ).filter(Operator.source == SourceEnum.primary).distinct().all()

    return len(combinaciones)

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

        # ── 4. Cargar datasets desde BD (PR 1) ────────────────────────────────
        from app.models.tables import SourceEnum
        dataset_publico = _cargar_scores_por_source(SourceEnum.public_synthetic)
        dataset_primario = _cargar_scores_por_source(SourceEnum.primary)
        categorias_cubiertas = _contar_categorias_cubiertas_primarias()

        # ── 5. Rebalanceo (motor 3.3) ─────────────────────────────────────────
        # Con n_valido=0 (sin respuestas primarias todavía) el motor devuelve
        # peso_primario=0 automáticamente (doc §9) — no hace falta un caso especial acá.
        rebalanceo_por_dim = {}
        distribuciones = {}
        for dim in scores:
            rb = self._rebalanceo.rebalancear(
                scores_publicos=dataset_publico.get(dim, []),
                scores_primarios=dataset_primario.get(dim, []),
                categorias_cubiertas=categorias_cubiertas,
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
        interp = self._interpretacion.interpretar(
            scores, benchmark_result, top_quartile_result,
            raw_answers=raw_answers, contexto=req.contexto.model_dump(),
        )

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

    def obtener_resultado(self, operator_id: str) -> ResultadoResponse | None:
        """Lee un resultado ya calculado desde DB (no recalcula)."""
        with get_session() as session:
            result = self._repo.obtener_resultado(session, operator_id)
            if result is None:
                return None
            return ResultadoResponse(
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
```

---

## 7. `app/models/database.py` — un cambio puntual

**Por qué**: Neon (Postgres serverless) cierra conexiones ociosas del lado del servidor. Sin `pool_pre_ping`, SQLAlchemy reutiliza una conexión ya muerta del pool en vez de abrir una nueva, y la primera consulta después de un rato sin tráfico falla con `sqlalchemy.exc.OperationalError: SSL connection has been closed unexpectedly`. Esto rompió el frontend en producción — el navegador lo reportaba como error de CORS porque nunca llegaba una respuesta HTTP real, no porque faltaran headers.

Buscar:
```python
_engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
```
Reemplazar por:
```python
_engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    # Neon (y otros Postgres serverless) cierran conexiones ociosas del lado del server.
    # Sin esto, la primera query tras un rato de inactividad falla con
    # "SSL connection has been closed unexpectedly" en vez de reconectar.
    pool_pre_ping=True,
    pool_recycle=300,
)
```
Nada más cambia en este archivo.

---

## 8. Endpoints — `app/api/routers.py` y `app/main.py`

**Por qué**: faltaba `GET /questionnaire` completo. `GET /resultados/{id}` y `GET /resultados/{id}/pdf` eran stubs con `raise HTTPException(status_code=404, ...)` hardcodeado y un comentario `# TODO: leer desde DB en PR de persistencia`, a pesar de que el repository ya tenía `obtener_resultado()` implementado y funcionando — solo faltaba invocarlo. Tampoco había middleware de CORS, así que el navegador iba a bloquear cualquier request desde un frontend en otro dominio.

**`app/api/routers.py`** — reemplazar el archivo completo:

```python
"""
Routers FastAPI — reciben, llaman al orquestador, devuelven.
No calculan nada.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException

from app.schemas.request import CuestionarioRequest
from app.schemas.response import PDFInputResponse, ResultadoResponse
from app.services.benchmark_service import BenchmarkService


def _construir_llm_client():
    """Gemini si hay API key configurada; si no, None → InterpretationEngine
    usa el fallback determinista (doc §7 — el sistema nunca falla por ausencia de LLM)."""
    if not os.environ.get("GEMINI_API_KEY"):
        return None
    from app.engines.llm_clients.gemini_client import GeminiClient
    return GeminiClient()


router = APIRouter()
_service = BenchmarkService(llm_client=_construir_llm_client())

_QUESTIONNAIRE_YAML_PATH = Path(__file__).parent.parent.parent / "config" / "questionnaire.yaml"


@router.get("/questionnaire")
def obtener_cuestionario() -> dict:
    """Devuelve config/questionnaire.yaml como JSON para que el frontend arme el formulario."""
    with open(_QUESTIONNAIRE_YAML_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


@router.post("/respuestas", response_model=ResultadoResponse, status_code=202)
def enviar_respuestas(req: CuestionarioRequest) -> ResultadoResponse:
    """Recibe el cuestionario completo y ejecuta el pipeline."""
    return _service.procesar(req)


@router.get("/resultados/{operator_id}", response_model=ResultadoResponse)
def obtener_resultado(operator_id: str) -> ResultadoResponse:
    """Devuelve el resultado calculado para un operador."""
    resultado = _service.obtener_resultado(operator_id)
    if resultado is None:
        raise HTTPException(status_code=404, detail="Resultado no encontrado")
    return resultado


@router.get("/resultados/{operator_id}/pdf", response_model=PDFInputResponse)
def obtener_pdf_input(operator_id: str) -> PDFInputResponse:
    """JSON estable para que Proyecto 5 genere el PDF."""
    resultado = _service.pdf_input(operator_id)
    if resultado is None:
        raise HTTPException(status_code=404, detail="Resultado no encontrado")
    return resultado
```

**`main.py` se mueve a `app/main.py`** (borrar el `main.py` de la raíz, crear `app/main.py`) — contenido completo:

```python
"""
Punto de entrada — crea la app y registra los routers.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import router
from app.models.database import create_tables

app = FastAPI(
    title="Benchmark de madurez — Data Centers",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.on_event("startup")
def startup():
    create_tables()


@app.get("/health")
def health():
    return {"status": "ok"}
```

**Importante**: al mover `main.py` a `app/main.py`, el comando para levantar el servidor cambia de `uvicorn main:app` a `uvicorn app.main:app`. Si hay algún script, Dockerfile, o config de deploy que use el comando viejo, hay que actualizarlo. También cualquier test que haga `from main import app` pasa a `from app.main import app`.

---

## 9. Cliente LLM — Gemini conectado al motor de interpretación

**Por qué**: `InterpretationEngine` ya tenía el `Protocol LLMClient` (interfaz) y el patrón fallback-si-falla, pero nadie instanciaba un cliente real en ningún lado — `BenchmarkService()` se creaba siempre sin `llm_client`, así que el diagnóstico terminaba siendo 100% el fallback determinista pese a que el motor "soportaba" LLM.

**Archivo nuevo**: `app/engines/llm_clients/__init__.py` (vacío, solo para que sea un paquete importable):
```python
```

**Archivo nuevo**: `app/engines/llm_clients/gemini_client.py`:
```python
"""
Adaptador de Gemini para InterpretationEngine (backlog §3.6, §7).

Implementa el Protocol LLMClient (app/engines/interpretation_engine.py):
solo redacción de texto a partir de hechos ya calculados. Nunca decide
scores, percentiles ni el perfil — eso llega ya resuelto en el prompt.

Si la librería o la API key no están disponibles, el motor de
interpretación cae solo al fallback determinista (no es responsabilidad
de este cliente manejar ese caso).
"""
from __future__ import annotations

import os

from google import genai

_DEFAULT_MODEL = "gemini-flash-latest"


class GeminiClient:
    def __init__(self, api_key: str | None = None, model: str = _DEFAULT_MODEL) -> None:
        api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY no configurada")
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def generar(self, prompt: str) -> str:
        resp = self._client.models.generate_content(model=self._model, contents=prompt)
        return resp.text or ""
```

Se conecta en `app/api/routers.py` (ver `_construir_llm_client()` en la sección 8 de esta guía) — solo se instancia si `GEMINI_API_KEY` está seteada en el entorno; si no, `_service = BenchmarkService(llm_client=None)` y todo sigue funcionando con el fallback, sin romper nada.

**Dependencia nueva**: agregar `"google-genai==2.2.0"` a `pyproject.toml` (ver sección 11 de esta guía sobre por qué esto rompe el build si no se ajustan también `httpx` y `pydantic`).

**Modelo usado**: `gemini-flash-latest`. Si la cuenta de Gemini que use Diego no tiene acceso a ese alias, correr esto para ver qué modelos están disponibles con su key:
```python
from google import genai
client = genai.Client(api_key="...")
for m in client.models.list():
    if "generateContent" in (m.supported_actions or []):
        print(m.name)
```

---

## 10. `app/engines/interpretation_engine.py` — dos cambios: firma nueva + prompt enriquecido

**Cambio 1** — `interpretar()` y `_redactar()` y `_construir_prompt()` pasan a recibir `raw_answers` y `contexto` (para que el LLM tenga señales cualitativas, no solo scores agregados — ver el punto siguiente sobre el prompt).

Buscar:
```python
    def interpretar(
        self,
        scores: dict[str, float],
        benchmark: BenchmarkResult,
        top_quartile: TopQuartileResult,
    ) -> InterpretacionResult:
        perfil = self._asignar_perfil(scores)
        friccion = self._friccion_principal(benchmark)
        diagnostico, uso_llm = self._redactar(perfil, friccion, scores, benchmark, top_quartile)

        return InterpretacionResult(
            perfil=perfil,
            friccion_principal=friccion,
            diagnostico_texto=diagnostico,
            uso_llm=uso_llm,
        )
```
Reemplazar por:
```python
    def interpretar(
        self,
        scores: dict[str, float],
        benchmark: BenchmarkResult,
        top_quartile: TopQuartileResult,
        raw_answers: dict[str, dict] | None = None,
        contexto: dict | None = None,
    ) -> InterpretacionResult:
        perfil = self._asignar_perfil(scores)
        friccion = self._friccion_principal(benchmark)
        diagnostico, uso_llm = self._redactar(
            perfil, friccion, scores, benchmark, top_quartile, raw_answers, contexto
        )

        return InterpretacionResult(
            perfil=perfil,
            friccion_principal=friccion,
            diagnostico_texto=diagnostico,
            uso_llm=uso_llm,
        )
```

**Cambio 2** — agregar las tablas de traducción de ids crudos a texto legible, justo después de `_PERFILES`:

```python
# Traducción de ids crudos (config/questionnaire.yaml) a texto legible —
# solo para armar el prompt del LLM, no afecta el scoring.
_INTERFAZ_FRICCION_LABELS = {
    "energia_cooling":  "energía–cooling",
    "cooling_workload": "cooling–workload",
    "workload_energia": "workload–energía",
    "no_sabria_decir":  "no identificada por el operador",
}

_BLOQUEANTE_LABELS = {
    "presupuesto":         "presupuesto",
    "autoridad_politica":  "falta de autoridad o decisión política interna",
    "herramientas":        "falta de herramientas técnicas",
    "personal":            "falta de personal capacitado",
    "nada":                "ninguno reportado",
}
```

**Cambio 3** — `_redactar()` y `_construir_prompt()` reciben y usan los dos parámetros nuevos. Contenido completo final de todo el archivo (más simple pegarlo entero que aplicar 4 cambios encadenados):

```python
"""
Motor de interpretación (backlog §3.6).

1. Asigna el perfil cualitativo mediante una regla determinística en Python.
   El LLM nunca elige el perfil: solo lo recibe calculado y lo explica.

2. Identifica la fricción principal (dimensión con percentil más bajo).

3. Redacta el diagnóstico:
   - Primero intenta con LLM (cliente inyectable).
   - Si el LLM falla o no está disponible → fallback determinista.
   El sistema nunca falla por ausencia de LLM.

Prompts en app/prompts/ — no hardcodeados en este archivo (backlog §7).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from app.engines.benchmark_engine import BenchmarkResult
from app.engines.top_quartile_engine import TopQuartileResult

# ── Perfiles cualitativos (reglas determinísticas) ────────────────────────────
# Umbrales sobre los scores por dimensión — no sobre percentiles.
# El LLM recibe el perfil ya calculado; nunca lo elige.

_UMBRALES_REACTIVO = {
    "latencia": 40.0,
    "visibilidad": 40.0,
}

_PERFILES = {
    "operacion_optimizada":  "Operación con alta coordinación entre capas",
    "coordinacion_parcial":  "Coordinación cross-layer en desarrollo",
    "operacion_reactiva":    "Operación reactiva con coordinación manual entre capas",
    "visibilidad_limitada":  "Visibilidad y coordinación cross-layer limitadas",
}

# Traducción de ids crudos (config/questionnaire.yaml) a texto legible —
# solo para armar el prompt del LLM, no afecta el scoring.
_INTERFAZ_FRICCION_LABELS = {
    "energia_cooling":  "energía–cooling",
    "cooling_workload": "cooling–workload",
    "workload_energia": "workload–energía",
    "no_sabria_decir":  "no identificada por el operador",
}

_BLOQUEANTE_LABELS = {
    "presupuesto":         "presupuesto",
    "autoridad_politica":  "falta de autoridad o decisión política interna",
    "herramientas":        "falta de herramientas técnicas",
    "personal":            "falta de personal capacitado",
    "nada":                "ninguno reportado",
}


@runtime_checkable
class LLMClient(Protocol):
    def generar(self, prompt: str) -> str: ...


@dataclass
class InterpretacionResult:
    perfil: str
    friccion_principal: str
    diagnostico_texto: str
    uso_llm: bool


class InterpretationEngine:
    """
    Motor de interpretación. Sin DB ni FastAPI.
    llm_client es opcional — si no se pasa, usa el fallback determinista.
    """

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm = llm_client
        self._prompt_tpl = self._cargar_prompt()

    def interpretar(
        self,
        scores: dict[str, float],
        benchmark: BenchmarkResult,
        top_quartile: TopQuartileResult,
        raw_answers: dict[str, dict] | None = None,
        contexto: dict | None = None,
    ) -> InterpretacionResult:
        perfil = self._asignar_perfil(scores)
        friccion = self._friccion_principal(benchmark)
        diagnostico, uso_llm = self._redactar(
            perfil, friccion, scores, benchmark, top_quartile, raw_answers, contexto
        )

        return InterpretacionResult(
            perfil=perfil,
            friccion_principal=friccion,
            diagnostico_texto=diagnostico,
            uso_llm=uso_llm,
        )

    # ── privados ──────────────────────────────────────────────────────────────

    def _asignar_perfil(self, scores: dict[str, float]) -> str:
        """
        Regla determinística sobre scores (doc §3.6).
        El LLM nunca elige el perfil.
        """
        lat = scores.get("latencia", 100.0)
        vis = scores.get("visibilidad", 100.0)
        promedio = sum(scores.values()) / len(scores) if scores else 0.0

        if lat < _UMBRALES_REACTIVO["latencia"] and vis < _UMBRALES_REACTIVO["visibilidad"]:
            return "operacion_reactiva"
        if vis < _UMBRALES_REACTIVO["visibilidad"]:
            return "visibilidad_limitada"
        if promedio >= 70.0:
            return "operacion_optimizada"
        return "coordinacion_parcial"

    @staticmethod
    def _friccion_principal(benchmark: BenchmarkResult) -> str:
        """Dimensión con el percentil relativo más bajo."""
        if not benchmark.dimensiones:
            return "latencia"
        return min(benchmark.dimensiones, key=lambda d: d.percentil).dimension

    def _redactar(
        self,
        perfil: str,
        friccion: str,
        scores: dict[str, float],
        benchmark: BenchmarkResult,
        top_quartile: TopQuartileResult,
        raw_answers: dict[str, dict] | None,
        contexto: dict | None,
    ) -> tuple[str, bool]:
        """Intenta LLM; si falla usa fallback determinista."""
        if self._llm is not None:
            try:
                prompt = self._construir_prompt(
                    perfil, friccion, scores, benchmark, top_quartile, raw_answers, contexto
                )
                texto = self._llm.generar(prompt)
                if texto and len(texto.strip()) > 20:
                    return texto.strip(), True
            except Exception:
                pass  # fallback a continuación

        return self._fallback(perfil, friccion, scores, benchmark), False

    def _fallback(
        self,
        perfil: str,
        friccion: str,
        scores: dict[str, float],
        benchmark: BenchmarkResult,
    ) -> str:
        """Diagnóstico determinista desde hechos estructurados. Específico, no genérico."""
        perfil_desc = _PERFILES.get(perfil, perfil)
        pd = benchmark.get(friccion)
        percentil_txt = f"percentil {pd.percentil:.0f}" if pd else "posición no disponible"

        score_friccion = scores.get(friccion, 0.0)
        labels = {
            "latencia":            "latencia de coordinación",
            "visibilidad":         "visibilidad cross-layer",
            "atribucion_friccion": "atribución de fricción",
            "auto_cuantificacion": "auto-cuantificación de capacidad",
            "bloqueantes":         "gestión de bloqueantes",
        }
        nombre_friccion = labels.get(friccion, friccion)

        return (
            f"Perfil: {perfil_desc}. "
            f"La dimensión con mayor oportunidad de mejora es {nombre_friccion} "
            f"(score {score_friccion:.0f}/100, {percentil_txt} en su grupo de referencia). "
            "Este resultado se basa en las respuestas reportadas y la distribución "
            "de operadores comparables."
        )

    def _construir_prompt(
        self,
        perfil: str,
        friccion: str,
        scores: dict[str, float],
        benchmark: BenchmarkResult,
        top_quartile: TopQuartileResult,
        raw_answers: dict[str, dict] | None,
        contexto: dict | None,
    ) -> str:
        if not self._prompt_tpl:
            return ""
        raw_answers = raw_answers or {}
        brechas = "\n".join(
            f"- {b.descripcion}" for b in top_quartile.brechas
        ) or "Sin brechas identificadas con el cuartil superior."

        contexto_txt = (
            f"facility {contexto.get('facility_size')}, tipo {contexto.get('dc_type')}, "
            f"región {contexto.get('region')}"
            if contexto else "no disponible"
        )

        interfaz_id = raw_answers.get("atribucion_friccion", {}).get("p1")
        interfaz_txt = _INTERFAZ_FRICCION_LABELS.get(interfaz_id, "no reportada")

        bloqueantes_ids = raw_answers.get("bloqueantes", {}).get("p1_bloqueantes") or []
        bloqueantes_txt = ", ".join(
            _BLOQUEANTE_LABELS.get(b, b) for b in bloqueantes_ids
        ) or "no reportados"

        auto = raw_answers.get("auto_cuantificacion", {})
        p1_cap = auto.get("p1_capacidad_total")
        p2_cap = auto.get("p2_capacidad_utilizable")
        unidad = auto.get("unidad", "")
        capacidad_txt = (
            f"{p1_cap} {unidad} instalada vs. {p2_cap} {unidad} utilizable"
            if p1_cap is not None and p2_cap is not None
            else "no reportada por el operador"
        )

        return self._prompt_tpl.format(
            perfil=perfil,
            friccion=friccion,
            scores=str(scores),
            brechas=brechas,
            contexto=contexto_txt,
            interfaz_friccion=interfaz_txt,
            bloqueantes_reportados=bloqueantes_txt,
            capacidad_texto=capacidad_txt,
        )

    @staticmethod
    def _cargar_prompt() -> str:
        path = Path(__file__).parent.parent / "prompts" / "diagnostico.txt"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""
```

---

## 11. `app/prompts/diagnostico.txt` — reemplazar el archivo completo

**Por qué**: el prompt original solo recibía `perfil`, `friccion`, `scores` agregados y `brechas` — el LLM terminaba redactando una versión en prosa de números que el operador ya ve en las cards de score, sin agregar diagnóstico real. Se reescribió dos veces: primero para incorporar las señales cualitativas (`interfaz_friccion`, `bloqueantes_reportados`, `capacidad_texto` — que llegan del cambio de la sección 10), y después para que el tono sea analítico/hipotético ("esto sugiere...") en vez de categórico ("tu problema es...").

Contenido completo final (esta es la versión que hay que usar — no la intermedia):

```
Eres un especialista en eficiencia operativa de data centers, con una mirada
analítica — no un oráculo que dictamina "tu problema es X". Redactás un
diagnóstico breve (3-4 oraciones) que RAZONA a partir de la evidencia, no que
la afirma de forma categórica.

Estructura del razonamiento (no lo muestres como lista, integralo en prosa):
1. Qué señal concreta (score, percentil o brecha) dispara la conclusión.
2. Por qué esa señal, combinada con el contexto de este operador (tamaño de
   facility, tipo de data center), es consistente con esa lectura — no la
   única explicación posible, sino la más respaldada por los datos.
3. Qué se podría observar a continuación para confirmar o refutar esa lectura.

Reglas:
- Preferí lenguaje de hipótesis razonada ("esto sugiere", "es consistente
  con", "un indicio de") sobre lenguaje categórico ("tu problema es",
  "esto significa que"). El objetivo es una lectura socrática, no un
  veredicto.
- No repitas los números de score tal cual — el operador ya los ve en
  pantalla. Citalos solo cuando sostienen un paso del razonamiento.
- No inventes datos que no estén en esta lista. No afirmes causalidad no
  demostrada — si dos señales son solo correlativas, decilo así.

Contexto del operador: {contexto}
Perfil asignado: {perfil}
Dimensión con mayor fricción: {friccion}
Scores por dimensión (0-100): {scores}
Brechas con el cuartil superior:
{brechas}

Señales diagnósticas adicionales (no entran al score, explican el porqué):
- Interfaz donde percibe mayor pérdida de capacidad: {interfaz_friccion}
- Bloqueantes reportados para resolver el problema: {bloqueantes_reportados}
- Capacidad instalada vs. utilizable: {capacidad_texto}

Responde solo con el texto del diagnóstico, sin encabezados ni listas.
```

---

## 12. `pyproject.toml` — dependencias

**Por qué**: al agregar `google-genai` (sección 9), su instalación entra en conflicto con las versiones ya fijadas de `httpx` y `pydantic` — un `pip install` limpio (el que corre Render en cada deploy) falla con `ResolutionImpossible`. No se detecta en un entorno local si ya hay versiones más nuevas instaladas de otros proyectos, hay que probarlo en un venv limpio para verlo.

Buscar (dentro de `dependencies = [...]`):
```toml
    "fastapi==0.111.0",
    "uvicorn[standard]==0.30.1",
    "pydantic==2.7.4",
    "pydantic-settings==2.3.4",
    "pyyaml==6.0.1",
    "sqlalchemy==2.0.30",
    "psycopg2-binary==2.9.9",
    "httpx==0.27.0",
    "python-ulid==2.2.0",
```
Reemplazar por:
```toml
    "fastapi==0.111.0",
    "uvicorn[standard]==0.30.1",
    "pydantic==2.9.2",
    "pydantic-settings==2.5.2",
    "pyyaml==6.0.1",
    "sqlalchemy==2.0.30",
    "psycopg2-binary==2.9.9",
    "httpx==0.28.1",
    "python-ulid==2.2.0",
    "google-genai==2.2.0",
```
(`google-genai` requiere `httpx>=0.28.1,<1.0.0` y `pydantic>=2.9.0,<3.0.0` — son las versiones mínimas compatibles, verificado instalando en un venv limpio.)

También se sacaron `alembic`, `scipy` y `numpy` de las dependencias — estaban declaradas pero sin un solo uso real en `app/` (confirmado con `git grep`), y `alembic` en particular no se usa porque `create_tables()` usa `Base.metadata.create_all()`, no migraciones. Si en `develop` siguen ahí y no las está usando nadie, se pueden sacar también, no es obligatorio.

---

## 13. `.gitignore` — bug que puede volver a pasar si tocan el frontend

**Por qué**: la regla `lib/` (para ignorar carpetas de entornos virtuales de Python) no tenía barra inicial, así que Git la interpretaba como "ignorar cualquier carpeta `lib` en cualquier nivel del repo" — no solo en la raíz. Esto hizo que `frontend/src/lib/` (donde vive la lógica de estado del formulario) nunca se subiera a git, aunque el resto de `frontend/` sí. Vercel clona limpio desde git, así que el build fallaba con `Cannot find module '../../lib/formState'` — en local nunca se notó porque los archivos SÍ existían en el filesystem.

Buscar:
```
lib/
lib64/
```
Reemplazar por:
```
/lib/
/lib64/
```
La barra inicial acota la regla a la raíz del repo únicamente. **Ojo con este patrón en general** — cualquier regla de `.gitignore` sin barra inicial aplica en todos los niveles del árbol, no solo en la carpeta donde parece estar pensada.

Agregar también (si no está), para la guía de despliegue de la sección 14:
```
# Guía de migración interna — nunca se commitea al repo
Guia_PRs_Migracion.md
```

---

## 14. Infraestructura de deploy (no es código, pero es necesario para que todo funcione)

Esto no está en el repo como código, es config externa — dejarlo documentado para que no se pierda:

- **Base de datos**: Neon (Postgres serverless). Variable de entorno `DATABASE_URL`.
- **LLM**: Gemini. Variable de entorno `GEMINI_API_KEY`. Sin ella, el sistema sigue funcionando con el fallback determinista (no rompe nada).
- **`.env` local**: crear uno en la raíz del repo (está en `.gitignore`, no se commitea) con:
  ```
  DATABASE_URL=postgresql://...
  GEMINI_API_KEY=...
  ```
- **Backend en Render**: hay un `render.yaml` en la raíz del repo con la config del servicio (`buildCommand: pip install .`, `startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT`). Si se crea el servicio a mano en el dashboard de Render en vez de vía Blueprint, hay que tipear esos comandos exactos — ojo con no dejar espacios de más ni de menos (`pip install .`, con espacio antes del punto, no `pip install.`).
- **`GET /health`** es el endpoint que Render usa para chequear que el servicio esté vivo.

---

## Checklist final para verificar que todo quedó bien

Antes de dar por terminado, correr en orden:

```bash
python -m pytest tests/ -q
```
Debería dar 178 passed / 2 failed (los 2 que fallan son preexistentes — dependen de que la BD ya esté sembrada con el dataset público antes de correr los tests, no un bug de este trabajo).

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Y en otra terminal:
```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/questionnaire
```
Ambos deberían responder 200.
