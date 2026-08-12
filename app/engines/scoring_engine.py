"""
Motor de scoring — convierte respuestas en scores por dimensión (backlog §3.1).

Implementa exactamente las fórmulas del Documento Metodológico §3-7:
  - Latencia:           (score_p1 + score_p2 + score_p3) / 3
  - Visibilidad:        (score_p1 + score_p2 + score_p3) / 3
  - Atribución:         (score_p2 + score_p3) / 2  [P1 es nominal]
  - Auto-cuantificación:(score_completitud_p1p2 + score_p3) / 2
  - Bloqueantes:        (score_cantidad_p1 + score_p2) / 2  [P1 nominal multi-sel]

Reglas:
- No importa FastAPI ni toca la base de datos.
- Todos los scores de 0 a 100.
- Las respuestas crudas se conservan para almacenamiento (doc §2.5).
- Los casos borde documentados se manejan aquí, no en el schema.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.config.loader import get_config
from app.schemas.request import CuestionarioRequest


@dataclass
class ScoreDetalle:
    """Score de una dimensión con desglose por pregunta."""
    dimension: str
    score: float                             # 0-100
    desglose: dict[str, float | int | None]  # pregunta → score parcial
    raw_answers: dict                        # respuestas crudas (doc §2.5)
    notas: list[str] = field(default_factory=list)


@dataclass
class ScoringResult:
    scores: list[ScoreDetalle]

    def get(self, dimension: str) -> ScoreDetalle | None:
        return next((s for s in self.scores if s.dimension == dimension), None)


class ScoringEngine:
    """
    Motor determinístico. Recibe CuestionarioRequest, devuelve ScoringResult.
    Sin estado — el mismo input siempre produce el mismo output.
    """

    def __init__(self) -> None:
        self._cfg = get_config()

    def score(self, req: CuestionarioRequest) -> ScoringResult:
        return ScoringResult(scores=[
            self._score_latencia(req),
            self._score_visibilidad(req),
            self._score_atribucion(req),
            self._score_auto_cuantificacion(req),
            self._score_bloqueantes(req),
        ])

    # ── Dimensión 1: Latencia (doc §3) ────────────────────────────────────────

    def _score_latencia(self, req: CuestionarioRequest) -> ScoreDetalle:
        lat = req.latencia
        cfg = self._cfg

        sp1 = cfg.score_numerico("latencia", "p1", lat.p1_minutos)
        sp2 = cfg.score_numerico("latencia", "p2", lat.p2_minutos)
        sp3 = cfg.score_categoria("latencia", "p3", lat.p3)

        score = (sp1 + sp2 + sp3) / 3

        return ScoreDetalle(
            dimension="latencia",
            score=round(score, 2),
            desglose={"p1": sp1, "p2": sp2, "p3": sp3},
            raw_answers={
                "p1_minutos": lat.p1_minutos,
                "p2_minutos": lat.p2_minutos,
                "p3": lat.p3,
            },
        )

    # ── Dimensión 2: Visibilidad (doc §4) ─────────────────────────────────────

    def _score_visibilidad(self, req: CuestionarioRequest) -> ScoreDetalle:
        vis = req.visibilidad
        cfg = self._cfg

        sp1 = cfg.score_numerico("visibilidad", "p1", float(vis.p1_sistemas))
        sp2 = cfg.score_categoria("visibilidad", "p2", vis.p2)
        sp3 = cfg.score_categoria("visibilidad", "p3", vis.p3)

        score = (sp1 + sp2 + sp3) / 3

        return ScoreDetalle(
            dimension="visibilidad",
            score=round(score, 2),
            desglose={"p1": sp1, "p2": sp2, "p3": sp3},
            raw_answers={
                "p1_sistemas": vis.p1_sistemas,
                "p2": vis.p2,
                "p3": vis.p3,
            },
        )

    # ── Dimensión 3: Atribución (doc §5) ──────────────────────────────────────

    def _score_atribucion(self, req: CuestionarioRequest) -> ScoreDetalle:
        atr = req.atribucion_friccion
        cfg = self._cfg
        notas = []

        # Caso borde (doc §5): si P1 = "no_sabria_decir", P2 y P3 → 0
        if atr.p1 == "no_sabria_decir":
            sp2 = sp3 = 0
            notas.append("P1='no_sabria_decir': P2 y P3 se asignaron 0 automáticamente")
        else:
            sp2 = cfg.score_categoria("atribucion_friccion", "p2", atr.p2)
            sp3 = cfg.score_categoria("atribucion_friccion", "p3", atr.p3)

        # P1 es nominal — no entra al índice (doc §2.6)
        score = (sp2 + sp3) / 2

        return ScoreDetalle(
            dimension="atribucion_friccion",
            score=round(score, 2),
            desglose={"p1_nominal": None, "p2": sp2, "p3": sp3},
            raw_answers={"p1": atr.p1, "p2": atr.p2, "p3": atr.p3},
            notas=notas,
        )

    # ── Dimensión 4: Auto-cuantificación (doc §6) ─────────────────────────────

    def _score_auto_cuantificacion(self, req: CuestionarioRequest) -> ScoreDetalle:
        aq = req.auto_cuantificacion
        cfg = self._cfg
        notas = []

        # Completitud y coherencia de P1/P2 (doc §6)
        p1 = aq.p1_capacidad_total
        p2 = aq.p2_capacidad_utilizable

        if p1 is not None and p2 is not None and p1 > 0 and p2 <= p1:
            score_completitud = 100
            pct_varada = round((p1 - p2) / p1 * 100, 2)
        else:
            score_completitud = 0
            pct_varada = None
            if p1 is None or p2 is None:
                notas.append("P1 o P2 no provistos: score_completitud=0")
            else:
                notas.append("P2 > P1 o valor inválido: score_completitud=0")

        sp3 = cfg.score_categoria("auto_cuantificacion", "p3", aq.p3)
        score = (score_completitud + sp3) / 2

        return ScoreDetalle(
            dimension="auto_cuantificacion",
            score=round(score, 2),
            desglose={"score_completitud_p1p2": score_completitud, "p3": sp3},
            raw_answers={
                "p1_capacidad_total": p1,
                "p2_capacidad_utilizable": p2,
                "unidad": aq.unidad,
                "p3": aq.p3,
                "pct_varada_calculado": pct_varada,
            },
            notas=notas,
        )

    # ── Dimensión 5: Bloqueantes (doc §7) ─────────────────────────────────────

    def _score_bloqueantes(self, req: CuestionarioRequest) -> ScoreDetalle:
        blk = req.bloqueantes
        cfg = self._cfg
        notas = []

        p1_lista = blk.p1_bloqueantes

        # Caso borde (doc §7): solo "nada" → P2 se autoasigna 100
        if p1_lista == ["nada"]:
            score_cantidad = 100
            sp2 = 100
            notas.append("Solo 'nada' seleccionado: P2 autoasignado 100")
        else:
            # Filtrar "nada" si aparece mezclado (el schema ya lo previene, doble check)
            reales = [b for b in p1_lista if b != "nada"]
            score_cantidad_pq = cfg.dimension("bloqueantes").pregunta("p1")
            score_cantidad = score_cantidad_pq.score_cantidad_bloqueantes(len(reales))
            sp2 = cfg.score_categoria("bloqueantes", "p2", blk.p2_severidad)

        score = (score_cantidad + sp2) / 2

        return ScoreDetalle(
            dimension="bloqueantes",
            score=round(score, 2),
            desglose={"score_cantidad_p1": score_cantidad, "p2": sp2},
            raw_answers={
                "p1_bloqueantes": p1_lista,
                "p2_severidad": blk.p2_severidad,
            },
            notas=notas,
        )
