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
