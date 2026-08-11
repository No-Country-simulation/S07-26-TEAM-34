"""
Motor de rebalanceo (backlog §3.3, doc metodológico §9).

Fórmula exacta del documento:
    peso_primario = (n_valido / (n_valido + k)) × factor_diversidad
    peso_publico  = 1 - peso_primario

Variables:
    n_valido:         respuestas primarias válidas acumuladas
    k = 50:           constante de suavizado (doc §9 — ajustable sin cambiar la lógica)
    factor_diversidad: proporción de categorías de segmentación cubiertas entre
                       las respuestas primarias (protege contra sesgo de auto-selección)

Casos borde documentados:
    - n_valido = 0 → peso_primario = 0 (100% público)
    - factor_diversidad = 0 → peso_primario = 0
    - Actualidad de datos: no implementada en MVP (doc §9 — mejora futura)

Salida: pesos + distribución combinada reconstruida.
El Motor 3.4 (benchmark) recibe la distribución ya lista, no la reconstruye.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from app.config.loader import get_config

# Constante de suavizado — doc §9: con k=50, n=50 → peso≈50%; n=200 → peso≈80%
K: int = 50

# Seed fijo para que el muestreo de _mezclar() sea reproducible
# (mismos inputs → mismos percentiles, requerido para tests determinísticos).
_SEED: int = 42


@dataclass
class RebalanceoResult:
    n_valido: int
    k: int
    factor_diversidad: float
    peso_primario: float    # [0.0, 1.0]
    peso_publico: float     # [0.0, 1.0]  = 1 - peso_primario
    distribucion_combinada: list[float]  # scores ya mezclados, listos para percentiles
    notas: list[str] = field(default_factory=list)


class RebalanceEngine:
    """
    Motor determinístico.
    Recibe los scores del dataset público y los del dataset primario,
    calcula los pesos y reconstruye la distribución combinada.
    """

    def __init__(self, k: int = K) -> None:
        self._k = k
        self._cfg = get_config()

    def rebalancear(
        self,
        scores_publicos: list[float],
        scores_primarios: list[float],
        categorias_cubiertas: int,
    ) -> RebalanceoResult:
        """
        Args:
            scores_publicos:      lista de scores del dataset sintético para una dimensión
            scores_primarios:     lista de scores de respuestas primarias válidas
            categorias_cubiertas: cantidad de combinaciones distintas de segmentación
                                  presentes en las respuestas primarias
        """
        n_valido = len(scores_primarios)
        total_categorias = self._cfg.segmentacion.total_categorias()

        # factor_diversidad = categorías cubiertas / total posibles (doc §9)
        factor_diversidad = (
            categorias_cubiertas / total_categorias
            if total_categorias > 0
            else 0.0
        )
        # Clamp a [0, 1]
        factor_diversidad = max(0.0, min(1.0, factor_diversidad))

        # Caso borde: sin datos primarios → peso_primario = 0 (doc §9)
        if n_valido == 0:
            peso_primario = 0.0
        else:
            peso_primario = (n_valido / (n_valido + self._k)) * factor_diversidad

        peso_primario = round(min(1.0, max(0.0, peso_primario)), 6)
        peso_publico = round(1.0 - peso_primario, 6)

        distribucion_combinada = self._mezclar(
            scores_publicos, peso_publico,
            scores_primarios, peso_primario,
        )

        notas = []
        if n_valido == 0:
            notas.append("Sin datos primarios: 100% referencia pública")
        if factor_diversidad < 0.3 and n_valido > 0:
            notas.append(
                f"Diversidad baja ({factor_diversidad:.1%}): peso primario frenado "
                "por concentración en pocos segmentos"
            )

        return RebalanceoResult(
            n_valido=n_valido,
            k=self._k,
            factor_diversidad=round(factor_diversidad, 4),
            peso_primario=peso_primario,
            peso_publico=peso_publico,
            distribucion_combinada=distribucion_combinada,
            notas=notas,
        )

    # ── privado ────────────────────────────────────────────────────────────────

    @staticmethod
    def _mezclar(
        publicos: list[float],
        w_pub: float,
        primarios: list[float],
        w_pri: float,
    ) -> list[float]:
        """
        Reconstruye la distribución combinada ponderando cada subconjunto.
        Devuelve la lista ordenada de scores para calcular percentiles.

        Implementación: submuestreo proporcional al peso.
        Con n total = max(len(publicos), 200) mantenemos estabilidad estadística.
        """
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

        combined = muestra_pub + muestra_pri
        combined.sort()
        return combined
