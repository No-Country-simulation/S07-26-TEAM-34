"""
Motor de interpretación (backlog §3.6).

1. Asigna el perfil cualitativo mediante una regla determinística en Python.
   El LLM nunca elige el perfil: solo lo recibe calculado y lo explica.

2. Identifica la fricción principal (dimensión con percentil más bajo).

3. Calcula el nivel de confianza de la comparación de forma determinística
   (a partir de n_valido/peso_primario del motor de rebalanceo — el LLM
   nunca decide esto, solo lo menciona en prosa).

4. Redacta el diagnóstico general (titular, razonamiento, acción sugerida)
   y una descripción analítica corta por cada una de las 5 dimensiones
   (no solo la de mayor fricción):
   - Primero intenta con LLM (cliente inyectable), pidiendo salida
     estructurada (JSON).
   - Si el LLM falla, no está disponible, o devuelve algo no parseable
     → fallback determinista, con la misma estructura.
   El sistema nunca falla por ausencia de LLM.

Prompts en app/prompts/ — no hardcodeados en este archivo (backlog §7).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from app.engines.benchmark_engine import BenchmarkResult
from app.engines.rebalance_engine import RebalanceoResult
from app.engines.top_quartile_engine import TopQuartileResult

# ── Perfiles cualitativos (reglas determinísticas) ────────────────────────────
# Umbrales sobre los scores por dimensión — no sobre percentiles.
# El LLM recibe el perfil ya calculado; nunca lo elige.

_UMBRALES_REACTIVO = {"latencia": 40.0, "visibilidad": 40.0}

_PERFILES = {
    "operacion_optimizada": "Operación con alta coordinación entre capas",
    "coordinacion_parcial": "Coordinación cross-layer en desarrollo",
    "operacion_reactiva":   "Operación reactiva con coordinación manual entre capas",
    "visibilidad_limitada": "Visibilidad y coordinación cross-layer limitadas",
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

_DIM_LABELS = {
    "latencia":            "latencia de coordinación",
    "visibilidad":         "visibilidad cross-layer",
    "atribucion_friccion": "atribución de fricción",
    "auto_cuantificacion": "auto-cuantificación de capacidad",
    "bloqueantes":         "gestión de bloqueantes",
}

# Qué mide cada dimensión — le da al LLM el "por qué" para redactar
# la descripción analítica por dimensión, sin tener que adivinarlo.
_DIM_QUE_MIDE = {
    "latencia": (
        "qué tan rápido se ajustan cooling y energía cuando cambia el "
        "workload, y cuánto de ese ajuste depende de intervención humana"
    ),
    "visibilidad": (
        "si hay una vista unificada de energía, cooling y workload, o si "
        "cada capa se gestiona de forma aislada"
    ),
    "atribucion_friccion": (
        "en qué interfaz entre capas percibe el operador que se pierde más "
        "capacidad, y qué tan basada en evidencia está esa percepción"
    ),
    "auto_cuantificacion": (
        "si el operador sabe, en números concretos, cuánta capacidad tiene "
        "varada, o si no tiene forma de cuantificarlo"
    ),
    "bloqueantes": (
        "qué le impediría al operador resolver el problema si supiera "
        "exactamente dónde está: presupuesto, política, herramientas o personal"
    ),
}

_DIMENSIONES_ORDEN = list(_DIM_LABELS.keys())


@runtime_checkable
class LLMClient(Protocol):
    def generar(
        self, prompt: str, system_instruction: str | None = None, json_output: bool = False
    ) -> str: ...


@dataclass
class InterpretacionResult:
    perfil: str
    friccion_principal: str
    titular: str
    diagnostico_texto: str          # el razonamiento — nombre conservado por compatibilidad
    accion_sugerida: str
    confianza_nivel: str            # "alto" | "medio" | "bajo"
    confianza_descripcion: str
    descripciones_por_dimension: dict[str, str]
    uso_llm: bool


class InterpretationEngine:
    """
    Motor de interpretación. Sin DB ni FastAPI.
    llm_client es opcional — si no se pasa, usa el fallback determinista.
    """

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm = llm_client
        self._prompt_tpl = self._cargar_prompt("diagnostico.txt")
        self._system_instruction = self._cargar_prompt("diagnostico_system.txt")

    def interpretar(
        self,
        scores: dict[str, float],
        benchmark: BenchmarkResult,
        top_quartile: TopQuartileResult,
        raw_answers: dict[str, dict] | None = None,
        contexto: dict | None = None,
        rebalanceo_por_dim: dict[str, RebalanceoResult] | None = None,
    ) -> InterpretacionResult:
        perfil = self._asignar_perfil(scores)
        friccion = self._friccion_principal(benchmark)
        confianza_nivel, confianza_desc = self._calcular_confianza(
            (rebalanceo_por_dim or {}).get(friccion)
        )

        titular, razonamiento, accion, por_dimension, uso_llm = self._redactar(
            perfil, friccion, scores, benchmark, top_quartile,
            raw_answers, contexto, confianza_desc,
        )

        return InterpretacionResult(
            perfil=perfil,
            friccion_principal=friccion,
            titular=titular,
            diagnostico_texto=razonamiento,
            accion_sugerida=accion,
            confianza_nivel=confianza_nivel,
            confianza_descripcion=confianza_desc,
            descripciones_por_dimension=por_dimension,
            uso_llm=uso_llm,
        )

    # ── privados ──────────────────────────────────────────────────────────────

    def _asignar_perfil(self, scores: dict[str, float]) -> str:
        """Regla determinística sobre scores (doc §3.6). El LLM nunca elige el perfil."""
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

    @staticmethod
    def _calcular_confianza(rb: RebalanceoResult | None) -> tuple[str, str]:
        """
        Nivel de confianza de la comparación — determinístico, a partir de
        n_valido/peso_primario del motor de rebalanceo (doc §9). El LLM
        nunca decide esto, solo lo menciona en el razonamiento.
        """
        if rb is None or rb.n_valido == 0:
            return (
                "bajo",
                "basada en datos simulados calibrados, todavía sin respuestas "
                "reales en este segmento",
            )
        if rb.peso_primario < 0.3:
            return (
                "medio",
                f"basada mayormente en datos simulados, con {rb.n_valido} "
                "respuesta(s) real(es) ya incorporada(s) a este segmento",
            )
        return (
            "alto",
            f"basada mayormente en {rb.n_valido} respuestas reales de "
            "operadores comparables en este segmento",
        )

    def _redactar(
        self,
        perfil: str,
        friccion: str,
        scores: dict[str, float],
        benchmark: BenchmarkResult,
        top_quartile: TopQuartileResult,
        raw_answers: dict[str, dict] | None,
        contexto: dict | None,
        confianza_desc: str,
    ) -> tuple[str, str, str, dict[str, str], bool]:
        """Intenta LLM (salida estructurada); si falla usa fallback determinista."""
        if self._llm is not None:
            try:
                prompt = self._construir_prompt(
                    perfil, friccion, scores, benchmark, top_quartile,
                    raw_answers, contexto, confianza_desc,
                )
                texto = self._llm.generar(
                    prompt, system_instruction=self._system_instruction, json_output=True
                )
                data = json.loads(texto)
                titular = str(data["titular"]).strip()
                razonamiento = str(data["razonamiento"]).strip()
                accion = str(data["accion_sugerida"]).strip()
                por_dim_raw = data.get("por_dimension") or {}
                por_dimension = {
                    dim: str(por_dim_raw[dim]).strip()
                    for dim in _DIMENSIONES_ORDEN
                    if dim in por_dim_raw and str(por_dim_raw[dim]).strip()
                }
                if titular and razonamiento and accion and len(por_dimension) == len(_DIMENSIONES_ORDEN):
                    return titular, razonamiento, accion, por_dimension, True
            except Exception:
                pass  # fallback a continuación

        titular, razonamiento, accion = self._fallback(perfil, friccion, scores, benchmark)
        por_dimension = self._fallback_por_dimension(scores, benchmark, top_quartile)
        return titular, razonamiento, accion, por_dimension, False

    def _fallback(
        self,
        perfil: str,
        friccion: str,
        scores: dict[str, float],
        benchmark: BenchmarkResult,
    ) -> tuple[str, str, str]:
        """Diagnóstico determinista desde hechos estructurados. Específico, no genérico."""
        perfil_desc = _PERFILES.get(perfil, perfil)
        pd = benchmark.get(friccion)
        percentil_txt = f"percentil {pd.percentil:.0f}" if pd else "posición no disponible"
        score_friccion = scores.get(friccion, 0.0)
        nombre_friccion = _DIM_LABELS.get(friccion, friccion)

        titular = f"Fricción principal: {nombre_friccion}"
        razonamiento = (
            f"Perfil: {perfil_desc}. "
            f"La dimensión con mayor oportunidad de mejora es {nombre_friccion} "
            f"(score {score_friccion:.0f}/100, {percentil_txt} en su grupo de referencia). "
            "Este resultado se basa en las respuestas reportadas y la distribución "
            "de operadores comparables."
        )
        accion = (
            f"Revisar en detalle las respuestas registradas para {nombre_friccion} "
            "junto con el equipo responsable de esa área."
        )
        return titular, razonamiento, accion

    @staticmethod
    def _fallback_por_dimension(
        scores: dict[str, float],
        benchmark: BenchmarkResult,
        top_quartile: TopQuartileResult,
    ) -> dict[str, str]:
        """Descripción determinista por dimensión — específica, no un placeholder vacío."""
        gaps = {b.dimension: b.descripcion for b in top_quartile.brechas}
        resultado: dict[str, str] = {}
        for dim in _DIMENSIONES_ORDEN:
            score = scores.get(dim, 0.0)
            pd = benchmark.get(dim)
            percentil = pd.percentil if pd else 50.0
            nombre = _DIM_LABELS.get(dim, dim)
            if dim in gaps:
                resultado[dim] = (
                    f"{nombre.capitalize()}: {score:.0f}/100, percentil {percentil:.0f} — "
                    f"por debajo del cuartil superior de su grupo comparable."
                )
            else:
                resultado[dim] = (
                    f"{nombre.capitalize()}: {score:.0f}/100, percentil {percentil:.0f} — "
                    f"en línea con el cuartil superior de su grupo comparable."
                )
        return resultado

    def _construir_prompt(
        self,
        perfil: str,
        friccion: str,
        scores: dict[str, float],
        benchmark: BenchmarkResult,
        top_quartile: TopQuartileResult,
        raw_answers: dict[str, dict] | None,
        contexto: dict | None,
        confianza_desc: str,
    ) -> str:
        if not self._prompt_tpl:
            return ""
        raw_answers = raw_answers or {}
        brechas = "\n".join(
            f"- {b.descripcion}" for b in top_quartile.brechas
        ) or "Sin brechas identificadas con el cuartil superior."

        detalle_dimensiones = "\n".join(
            f"- {_DIM_LABELS.get(dim, dim)} (qué mide: {_DIM_QUE_MIDE.get(dim, '')}): "
            f"score {scores.get(dim, 0.0):.0f}/100, "
            f"percentil {(benchmark.get(dim).percentil if benchmark.get(dim) else 50.0):.0f}"
            for dim in _DIMENSIONES_ORDEN
        )

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
            detalle_dimensiones=detalle_dimensiones,
            brechas=brechas,
            contexto=contexto_txt,
            interfaz_friccion=interfaz_txt,
            bloqueantes_reportados=bloqueantes_txt,
            capacidad_texto=capacidad_txt,
            confianza_descripcion=confianza_desc,
        )

    @staticmethod
    def _cargar_prompt(nombre: str) -> str:
        path = Path(__file__).parent.parent / "prompts" / nombre
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""
