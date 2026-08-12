"""
Motor de interpretación (backlog §3.6).

1. Perfil por regla determinística — el LLM nunca lo elige.
2. Fricción principal = dimensión con percentil más bajo.
3. Diagnóstico: LLM si disponible, fallback determinista si no.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from app.engines.benchmark_engine import BenchmarkResult
from app.engines.top_quartile_engine import TopQuartileResult

_UMBRALES_REACTIVO = {"latencia": 40.0, "visibilidad": 40.0}

_PERFILES = {
    "operacion_optimizada": "Operación con alta coordinación entre capas",
    "coordinacion_parcial": "Coordinación cross-layer en desarrollo",
    "operacion_reactiva":   "Operación reactiva con coordinación manual entre capas",
    "visibilidad_limitada": "Visibilidad y coordinación cross-layer limitadas",
}

_INTERFAZ_FRICCION_LABELS = {
    "energia_cooling":  "energía–cooling",
    "cooling_workload": "cooling–workload",
    "workload_energia": "workload–energía",
    "no_sabria_decir":  "no identificada por el operador",
}

_BLOQUEANTE_LABELS = {
    "presupuesto":        "presupuesto",
    "autoridad_politica": "falta de autoridad o decisión política interna",
    "herramientas":       "falta de herramientas técnicas",
    "personal":           "falta de personal capacitado",
    "nada":               "ninguno reportado",
}

_DIM_LABELS = {
    "latencia":            "latencia de coordinación",
    "visibilidad":         "visibilidad cross-layer",
    "atribucion_friccion": "atribución de fricción",
    "auto_cuantificacion": "auto-cuantificación de capacidad",
    "bloqueantes":         "gestión de bloqueantes",
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

    def _asignar_perfil(self, scores: dict[str, float]) -> str:
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
                pass
        return self._fallback(perfil, friccion, scores, benchmark), False

    def _fallback(self, perfil, friccion, scores, benchmark) -> str:
        perfil_desc = _PERFILES.get(perfil, perfil)
        pd = benchmark.get(friccion)
        percentil_txt = f"percentil {pd.percentil:.0f}" if pd else "posición no disponible"
        nombre_friccion = _DIM_LABELS.get(friccion, friccion)
        score_friccion = scores.get(friccion, 0.0)
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
