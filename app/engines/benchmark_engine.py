"""
Motor de benchmark y percentiles (backlog §3.4, doc §9).

Calcula la posición relativa del operador dentro de su grupo comparable.
Usa la distribución combinada que ya entregó el Motor de rebalanceo (3.3).

Estadística robusta: mediana y cuartiles, no promedio (backlog §3.4).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PercentilDimension:
    dimension: str
    score_operador: float       # 0-100
    percentil: float            # 0-100: posición relativa
    mediana_ref: float          # mediana de la distribución combinada
    p25_ref: float              # cuartil inferior
    p75_ref: float              # cuartil superior (umbral top 25%)
    n_referencia: int           # tamaño de la distribución usada
    grupo_comparable: str


@dataclass
class BenchmarkResult:
    dimensiones: list[PercentilDimension]
    grupo_comparable: str

    def get(self, dimension: str) -> PercentilDimension | None:
        return next((d for d in self.dimensiones if d.dimension == dimension), None)


class BenchmarkEngine:
    """
    Motor determinístico.
    Recibe los scores del operador y la distribución combinada
    (ya reconstruida por RebalanceEngine), calcula percentiles.
    """

    def calcular(
        self,
        scores_operador: dict[str, float],
        distribuciones: dict[str, list[float]],
        grupo_comparable: str,
    ) -> BenchmarkResult:
        """
        Args:
            scores_operador:  {dimension: score 0-100}
            distribuciones:   {dimension: lista de scores de la distribución combinada}
            grupo_comparable: identificador del grupo usado
        """
        dimensiones = []
        for dim, score in scores_operador.items():
            dist = distribuciones.get(dim, [])
            dimensiones.append(
                self._percentil_dimension(dim, score, dist, grupo_comparable)
            )

        return BenchmarkResult(
            dimensiones=dimensiones,
            grupo_comparable=grupo_comparable,
        )

    # ── privado ────────────────────────────────────────────────────────────────

    @staticmethod
    def _percentil_dimension(
        dimension: str,
        score: float,
        distribucion: list[float],
        grupo: str,
    ) -> PercentilDimension:
        if not distribucion:
            return PercentilDimension(
                dimension=dimension,
                score_operador=score,
                percentil=50.0,   # sin referencia → posición neutral
                mediana_ref=50.0,
                p25_ref=25.0,
                p75_ref=75.0,
                n_referencia=0,
                grupo_comparable=grupo,
            )

        dist_sorted = sorted(distribucion)
        n = len(dist_sorted)

        # Percentil del operador: % de la distribución que está por debajo
        por_debajo = sum(1 for s in dist_sorted if s < score)
        percentil = round((por_debajo / n) * 100, 1)

        # Estadísticas robustas (mediana y cuartiles, doc §3.4)
        mediana = _quantile(dist_sorted, 0.50)
        p25 = _quantile(dist_sorted, 0.25)
        p75 = _quantile(dist_sorted, 0.75)

        return PercentilDimension(
            dimension=dimension,
            score_operador=score,
            percentil=percentil,
            mediana_ref=round(mediana, 2),
            p25_ref=round(p25, 2),
            p75_ref=round(p75, 2),
            n_referencia=n,
            grupo_comparable=grupo,
        )


def _quantile(sorted_data: list[float], q: float) -> float:
    """Cuantil por interpolación lineal (método estándar)."""
    n = len(sorted_data)
    if n == 0:
        return 0.0
    if n == 1:
        return sorted_data[0]
    idx = q * (n - 1)
    lo = int(idx)
    hi = lo + 1
    if hi >= n:
        return sorted_data[-1]
    frac = idx - lo
    return sorted_data[lo] + frac * (sorted_data[hi] - sorted_data[lo])
