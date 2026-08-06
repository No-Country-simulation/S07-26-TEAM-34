"""Tests PR 10 — Motor de privacidad liviana (backlog §3.7)."""
from __future__ import annotations
import uuid
from app.engines.privacy_engine import PrivacyEngine


def test_genera_uuid_valido():
    pid = PrivacyEngine.generar_operator_id()
    parsed = uuid.UUID(pid)
    assert parsed.version == 4


def test_cada_llamada_genera_id_distinto():
    ids = {PrivacyEngine.generar_operator_id() for _ in range(100)}
    assert len(ids) == 100


def test_id_no_contiene_datos_del_operador():
    """El UUID no debe contener texto identificable."""
    pid = PrivacyEngine.generar_operator_id()
    for dato in ["borges", "empresa", "latam", "colo", "@"]:
        assert dato not in pid.lower()
