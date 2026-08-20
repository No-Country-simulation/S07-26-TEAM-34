"""
Adaptador de Gemini para InterpretationEngine (backlog §3.6, §7).

Implementa el Protocol LLMClient (app/engines/interpretation_engine.py):
solo redacción de texto a partir de hechos ya calculados. Nunca decide
scores, percentiles ni el perfil — eso llega ya resuelto en el prompt.

Temperatura baja (0.3 por default): esto se presenta como un diagnóstico
analítico, no contenido creativo — dos operadores con inputs casi
idénticos deberían recibir un razonamiento consistente, no uno que
varíe de tono según el azar del muestreo.

Cascada de modelos: si el primero de la lista falla (error de API, alta
demanda, etc.) se reintenta con el siguiente, en orden. Flash primero
(rápido/barato, el caso normal), Pro como respaldo de mayor calidad,
Flash-lite como último intento antes de agotar la cascada.

Si la librería, la API key, o los tres modelos fallan, el motor de
interpretación cae al fallback determinista (no es responsabilidad de
este cliente manejar ese caso — solo propaga la excepción).
"""
from __future__ import annotations

import os

from google import genai
from google.genai import types

_MODEL_CASCADE: tuple[str, ...] = (
    "gemini-flash-latest",
    "gemini-pro-latest",
    "gemini-flash-lite-latest",
)

_DEFAULT_TEMPERATURE = 0.3


class GeminiClient:
    def __init__(
        self,
        api_key: str | None = None,
        models: tuple[str, ...] = _MODEL_CASCADE,
        temperature: float = _DEFAULT_TEMPERATURE,
    ) -> None:
        api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY no configurada")
        self._client = genai.Client(api_key=api_key)
        self._models = models
        self._temperature = temperature

    def generar(
        self,
        prompt: str,
        system_instruction: str | None = None,
        json_output: bool = False,
    ) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=self._temperature,
            response_mime_type="application/json" if json_output else "text/plain",
        )
        errores: list[str] = []

        for modelo in self._models:
            try:
                resp = self._client.models.generate_content(
                    model=modelo, contents=prompt, config=config
                )
                if resp.text:
                    return resp.text
                errores.append(f"{modelo}: respuesta vacía")
            except Exception as e:
                errores.append(f"{modelo}: {e}")
                continue

        raise RuntimeError(f"Los {len(self._models)} modelos de la cascada fallaron: {errores}")
