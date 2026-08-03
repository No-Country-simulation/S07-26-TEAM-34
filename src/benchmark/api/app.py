"""Punto de entrada FastAPI."""
from __future__ import annotations

from fastapi import FastAPI

from benchmark.api.routes import router
from benchmark.api.admin_routes import admin_router

app = FastAPI(
    title="Benchmark de madurez — Data Centers",
    version="0.1.0",
    description="Motor de benchmark operativo. Los motores calculan; el LLM interpreta.",
)

app.include_router(router)
app.include_router(admin_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
