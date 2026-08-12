"""
Adaptador de Gemini para InterpretationEngine (backlog §3.6, §7).

Solo redacta texto desde hechos ya calculados.
Nunca decide scores, percentiles ni perfil — eso llega resuelto en el prompt.
"""
from __future__ import annotations

import os

_DEFAULT_MODEL = "gemini-flash-latest"


class GeminiClient:
    def __init__(self, api_key: str | None = None, model: str = _DEFAULT_MODEL) -> None:
        api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY no configurada")
        from google import genai
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def generar(self, prompt: str) -> str:
        resp = self._client.models.generate_content(model=self._model, contents=prompt)
        return resp.text or ""
