"""
Carga y valida la configuración metodológica desde archivos YAML versionados.

La config define la metodología; el código implementa los mecanismos.
Una config inválida bloquea el inicio del sistema. (ADR-009)
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

from benchmark.domain.models import (
    CohortHierarchyConfig,
    PrivacyConfig,
    QuestionnaireConfig,
)


def _config_root() -> Path:
    """
    Resuelve la raíz de config/methodology en orden:
    1. Variable de entorno BENCHMARK_CONFIG_ROOT
    2. config/methodology relativo al directorio de trabajo
    3. Tres niveles arriba de este archivo (instalación en src/)
    """
    env = os.environ.get("BENCHMARK_CONFIG_ROOT")
    if env:
        return Path(env)
    cwd_candidate = Path.cwd() / "config" / "methodology"
    if cwd_candidate.exists():
        return cwd_candidate
    return Path(__file__).parent.parent.parent.parent / "config" / "methodology"


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_questionnaire(version: str) -> QuestionnaireConfig:
    """Carga y valida el cuestionario para una versión metodológica."""
    path = _config_root() / version / "questionnaire.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Cuestionario no encontrado para versión {version}: {path}")
    data = _load_yaml(path)
    config = QuestionnaireConfig.model_validate(data)
    if config.status != "published":
        raise ValueError(
            f"Cuestionario versión {version} no está publicado (status={config.status})"
        )
    return config


def load_cohort_hierarchy(version: str) -> CohortHierarchyConfig:
    """Carga la jerarquía de cohortes para una versión metodológica."""
    path = _config_root() / version / "cohorts.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"Config de cohortes no encontrada para versión {version}: {path}"
        )
    data = _load_yaml(path)
    return CohortHierarchyConfig.model_validate(data)


def load_privacy_config(version: str) -> PrivacyConfig:
    """Carga la configuración de privacidad para una versión metodológica."""
    path = _config_root() / version / "privacy.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"Config de privacidad no encontrada para versión {version}: {path}"
        )
    data = _load_yaml(path)
    return PrivacyConfig.model_validate(data)


def list_available_versions() -> list[str]:
    """Devuelve versiones metodológicas disponibles."""
    root = _config_root()
    if not root.exists():
        return []
    return sorted(
        d.name for d in root.iterdir()
        if d.is_dir() and (d / "questionnaire.yaml").exists()
    )


@lru_cache(maxsize=8)
def cached_questionnaire(version: str) -> QuestionnaireConfig:
    return load_questionnaire(version)


@lru_cache(maxsize=8)
def cached_cohort_hierarchy(version: str) -> CohortHierarchyConfig:
    return load_cohort_hierarchy(version)


@lru_cache(maxsize=8)
def cached_privacy_config(version: str) -> PrivacyConfig:
    return load_privacy_config(version)
