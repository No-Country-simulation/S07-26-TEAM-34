"""
Motor de comparación con el cuartil superior (backlog §3.5).

Selecciona operadores desde el percentil 75 y compara sus respuestas
con las del nuevo operador, dimensión por dimensión.
Salida: brechas concretas contra el top 25%.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BrechaTopQuartile:
    dimension: str
    descripcion: str       # texto específico, no genérico
    score_operador: float
    umbral_top25: float    # p75 de la distribución


@dataclass
class TopQuartileResult:
    brechas: list[BrechaTopQuartile]
    dimensiones_en_top: list[str]   # dimensiones donde el operador ya está en top 25%

    def get(self, dimension: str) -> BrechaTopQuartile | None:
        return next((b for b in self.brechas if b.dimension == dimension), None)


class TopQuartileEngine:
    """
    Recibe los percentiles del operador y los umbrales p75 por dimensión.
    Devuelve brechas concretas donde el operador está por debajo del top 25%.
    Sin DB, sin FastAPI.
    """

    def analizar(
        self,
        scores_operador: dict[str, float],
        percentiles_operador: dict[str, float],
        umbrales_p75: dict[str, float],
    ) -> TopQuartileResult:
        brechas: list[BrechaTopQuartile] = []
        en_top: list[str] = []

        for dim, score in scores_operador.items():
            percentil = percentiles_operador.get(dim, 50.0)
            p75 = umbrales_p75.get(dim, 75.0)

            if percentil >= 75.0:
                en_top.append(dim)
                continue

            diferencia = round(p75 - score, 1)
            descripcion = self._descripcion_brecha(dim, score, p75, diferencia)

            brechas.append(BrechaTopQuartile(
                dimension=dim,
                descripcion=descripcion,
                score_operador=score,
                umbral_top25=p75,
            ))

        return TopQuartileResult(brechas=brechas, dimensiones_en_top=en_top)

    @staticmethod
    def _descripcion_brecha(dim: str, score: float, p75: float, diff: float) -> str:
        labels = {
            "latencia":            "Latencia de coordinación",
            "visibilidad":         "Visibilidad cross-layer",
            "atribucion_friccion": "Atribución de fricción",
            "auto_cuantificacion": "Auto-cuantificación",
            "bloqueantes":         "Bloqueantes",
        }
        nombre = labels.get(dim, dim)
        return (
            f"{nombre}: el operador obtuvo {score:.0f}/100. "
            f"El cuartil superior alcanza {p75:.0f}/100 en este grupo "
            f"(diferencia: {diff:.0f} puntos)."
        )
