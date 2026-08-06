"""
Motor de privacidad y agregación, versión liviana (backlog §3.7).

Versión MVP — recortado explícitamente en el backlog:
  ✅ UUID aleatorio por respuesta, sin relación con nombre/email/empresa/IP
  ✅ El formulario no captura PII — no hay nada que encriptar
  ❌ Sin supresión de grupos pequeños (fuera de scope MVP)
  ❌ Sin auditoría de accesos o cambios (fuera de scope MVP)

Salida: operator_id anónimo listo para persistir.
"""
from __future__ import annotations

import uuid


class PrivacyEngine:
    """
    Motor liviano. Genera el ID anónimo.
    Sin estado. Sin DB. Sin FastAPI.
    """

    @staticmethod
    def generar_operator_id() -> str:
        """UUID v4 aleatorio — sin relación con ningún dato del operador."""
        return str(uuid.uuid4())
