"""
conftest.py global — crea las tablas de DB antes de los tests de integración.
"""
import pytest
from app.models.database import Base, get_engine


@pytest.fixture(scope="session", autouse=True)
def crear_tablas():
    """Crea todas las tablas antes de la sesión de tests."""
    Base.metadata.create_all(get_engine())
    yield
    # No se borran — SQLite en archivo, suficiente para tests locales
