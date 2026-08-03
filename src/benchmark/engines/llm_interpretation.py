"""
T-06-3: Flujo LLM con aprobación humana. (ADR-008)

El LLM genera propuestas de texto a partir de hechos estructurados.
Las propuestas NUNCA se publican directamente — requieren aprobación humana.
El fallback determinista siempre está disponible.

Invariantes:
- El LLM no calcula scores, percentiles, pesos ni agregados.
- Sin proveedor LLM → fallback determinista, el sistema sigue funcionando.
- Las propuestas se almacenan como PENDING hasta aprobación explícita.
- Los prompts están versionados y nunca contienen reglas de negocio.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class ProposalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ProposalType(str, Enum):
    NARRATIVE_ENRICHMENT = "narrative_enrichment"   # mejora de texto de un reporte
    METHODOLOGY_SUGGESTION = "methodology_suggestion"  # sugerencia de cambio metodológico
    FRICTION_LABEL = "friction_label"               # etiqueta de perfil de fricción


@dataclass
class LLMProposal:
    proposal_id: str
    proposal_type: ProposalType
    status: ProposalStatus
    source_facts: dict[str, Any]       # hechos estructurados que alimentaron el prompt
    prompt_version: str
    generated_text: str                # output del LLM (o fallback)
    used_llm: bool                     # False si se usó el fallback
    created_at: datetime
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_notes: str | None = None


# ── Prompts versionados ───────────────────────────────────────────────────────
# Los prompts están aquí, no en código de negocio. (ADR-009)
# Versionar junto con la metodología.

PROMPT_VERSION = "1.0.0"

_PROMPT_NARRATIVE = """Eres un redactor técnico especializado en eficiencia de data centers.
Tienes los siguientes hechos estructurados sobre el resultado de un operador:

Dimensión principal con fricción: {friction_dimension}
Severidad: {severity}
Bloqueantes identificados: {blockers}
Descripción base: {base_description}
Percentil en dimensión principal: {percentile}
Cohort usado: {cohort_label}

Escribe UN párrafo de 2-3 oraciones que:
1. Describa la situación específica sin afirmar causalidad.
2. Mencione la brecha concreta con el cuartil superior si existe.
3. Use lenguaje técnico pero accesible.

No inventes datos. No generalices. Basa la redacción solo en los hechos proporcionados."""

_PROMPT_METHODOLOGY = """Eres un analista de metodología de benchmarks.
Tienes las siguientes métricas del sistema:

Dimensión con mayor drift reciente: {drift_dimension}
Valor del drift: {drift_value}
n_effective actual: {n_effective}
Tendencia de acceptance rate: {acceptance_trend}

Propón UNA acción concreta y específica para mejorar la calidad del benchmark en esta dimensión.
La propuesta debe ser verificable y no debe implicar cambios en el scoring sin validación estadística.
Máximo 3 oraciones."""


class LLMInterpretationEngine:
    """
    Genera propuestas de texto asistidas por LLM.

    El cliente LLM es inyectable — en producción usar OpenAI, Anthropic, Bedrock, etc.
    Si no se inyecta cliente, usa el fallback determinista.
    """

    def __init__(self, llm_client: Any | None = None) -> None:
        self._client = llm_client

    def propose_narrative(
        self,
        proposal_id: str,
        friction_dimension: str,
        severity: str,
        blockers: list[str],
        base_description: str,
        percentile: float | None,
        cohort_label: str,
    ) -> LLMProposal:
        facts = {
            "friction_dimension": friction_dimension,
            "severity": severity,
            "blockers": blockers or ["ninguno identificado"],
            "base_description": base_description,
            "percentile": f"{percentile:.0f}" if percentile else "no disponible",
            "cohort_label": cohort_label,
        }

        text, used_llm = self._generate(
            _PROMPT_NARRATIVE.format(**{k: v if not isinstance(v, list) else ", ".join(v)
                                        for k, v in facts.items()}),
            fallback=base_description,
        )

        return LLMProposal(
            proposal_id=proposal_id,
            proposal_type=ProposalType.NARRATIVE_ENRICHMENT,
            status=ProposalStatus.PENDING,
            source_facts=facts,
            prompt_version=PROMPT_VERSION,
            generated_text=text,
            used_llm=used_llm,
            created_at=datetime.utcnow(),
        )

    def propose_methodology_action(
        self,
        proposal_id: str,
        drift_dimension: str,
        drift_value: float,
        n_effective: int,
        acceptance_trend: str,
    ) -> LLMProposal:
        facts = {
            "drift_dimension": drift_dimension,
            "drift_value": f"{drift_value:.3f}",
            "n_effective": str(n_effective),
            "acceptance_trend": acceptance_trend,
        }

        fallback = (
            f"Revisar preguntas de la dimensión '{drift_dimension}' "
            f"dado drift de {drift_value:.3f} y n_effective={n_effective}. "
            "Considerar ampliar la muestra antes del próximo snapshot."
        )

        text, used_llm = self._generate(
            _PROMPT_METHODOLOGY.format(**facts),
            fallback=fallback,
        )

        return LLMProposal(
            proposal_id=proposal_id,
            proposal_type=ProposalType.METHODOLOGY_SUGGESTION,
            status=ProposalStatus.PENDING,
            source_facts=facts,
            prompt_version=PROMPT_VERSION,
            generated_text=text,
            used_llm=used_llm,
            created_at=datetime.utcnow(),
        )

    # ── privados ──────────────────────────────────────────────────────────────

    def _generate(self, prompt: str, fallback: str) -> tuple[str, bool]:
        """
        Intenta generar texto con el LLM.
        Si falla o no hay cliente → retorna fallback determinista.
        """
        if self._client is None:
            return fallback, False
        try:
            result = self._client.generate(prompt)
            return result, True
        except Exception:
            # Nunca fallar por ausencia de LLM (ADR-008)
            return fallback, False


# ── Almacén de propuestas en memoria (reemplazar con tabla DB en producción) ──

_proposals_store: dict[str, LLMProposal] = {}


def save_proposal(proposal: LLMProposal) -> None:
    _proposals_store[proposal.proposal_id] = proposal


def get_proposal(proposal_id: str) -> LLMProposal | None:
    return _proposals_store.get(proposal_id)


def approve_proposal(
    proposal_id: str,
    reviewed_by: str,
    notes: str = "",
) -> LLMProposal | None:
    p = _proposals_store.get(proposal_id)
    if p is None:
        return None
    p.status = ProposalStatus.APPROVED
    p.reviewed_by = reviewed_by
    p.reviewed_at = datetime.utcnow()
    p.review_notes = notes
    return p


def reject_proposal(
    proposal_id: str,
    reviewed_by: str,
    notes: str = "",
) -> LLMProposal | None:
    p = _proposals_store.get(proposal_id)
    if p is None:
        return None
    p.status = ProposalStatus.REJECTED
    p.reviewed_by = reviewed_by
    p.reviewed_at = datetime.utcnow()
    p.review_notes = notes
    return p


def list_pending_proposals() -> list[LLMProposal]:
    return [p for p in _proposals_store.values() if p.status == ProposalStatus.PENDING]
