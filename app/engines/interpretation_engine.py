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
    ) -> tuple[str, bool]:
        """Intenta LLM; si falla usa fallback determinista."""
        if self._llm is not None:
            try:
                prompt = self._construir_prompt(perfil, friccion, scores, benchmark, top_quartile)
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
    ) -> str:
        if not self._prompt_tpl:
            return ""
        brechas = "\n".join(
            f"- {b.descripcion}" for b in top_quartile.brechas
        ) or "Sin brechas identificadas con el cuartil superior."

        return self._prompt_tpl.format(
            perfil=perfil,
            friccion=friccion,
            scores=str(scores),
            brechas=brechas,
        )

    @staticmethod
    def _cargar_prompt() -> str:
        path = Path(__file__).parent.parent / "prompts" / "diagnostico.txt"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""
