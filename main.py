"""
Punto de entrada — crea la app y registra los routers.
"""
from fastapi import FastAPI

from app.api.routers import router
from app.models.database import create_tables

app = FastAPI(
    title="Benchmark de madurez — Data Centers",
    version="1.0.0",
)

app.include_router(router, prefix="/api/v1")


@app.on_event("startup")
def startup():
    create_tables()


@app.get("/health")
def health():
    return {"status": "ok"}
