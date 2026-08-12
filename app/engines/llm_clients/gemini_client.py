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
