"""
Seed del dataset público sintético (PR 1 — Guia_PRs_Migracion.md).

Genera dataset_publico_sintetico.csv usando faker para datos realistas
y carga las filas en las tablas operators y dimension_scores con source="public_synthetic".

Uso:
    python -m config.seed_public_dataset [--force] [--n-registros N]
    o desde la raíz:
    python config/seed_public_dataset.py [--force] [--n-registros N]
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml
from faker import Faker

# Añadir el directorio raíz al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.loader import get_config
from app.models.database import Base, get_engine, get_session
from app.models.tables import DimensionEnum, DimensionScore, Operator, SourceEnum


# ── Configuración ───────────────────────────────────────────────────────────────

DATASET_CSV_PATH = Path(__file__).parent / "dataset_publico_sintetico.csv"
DEFAULT_N_REGISTROS = 1000


# ── Generación de datos sintéticos ───────────────────────────────────────────────

def generar_registro_sintetico(faker: Faker, cfg, yaml_data: dict) -> dict:
    """
    Genera un registro sintético realista usando faker y las opciones del YAML.
    Devuelve un dict con todos los campos necesarios para el CSV.
    """
    # Campos de contexto (segmentación)
    facility_size = random.choice(cfg.segmentacion.opciones("facility_size"))
    region = random.choice(cfg.segmentacion.opciones("region"))
    dc_type = random.choice(cfg.segmentacion.opciones("dc_type"))

    # Respuestas sintéticas por dimensión
    respuestas = {}

    # Latencia
    lat_cfg = cfg.dimension("latencia")
    respuestas["lat_p1_minutos"] = random.choice([1, 3, 10, 30, 120, 500, 2000])
    respuestas["lat_p2_minutos"] = random.choice([1, 3, 10, 30, 120, 500, 2000])
    respuestas["lat_p3"] = random.choice(lat_cfg.pregunta("p3").opciones_ids())

    # Visibilidad
    vis_cfg = cfg.dimension("visibilidad")
    respuestas["vis_p1_sistemas"] = random.choice([1, 2, 3, 4, 5])
    respuestas["vis_p2"] = random.choice(vis_cfg.pregunta("p2").opciones_ids())
    respuestas["vis_p3"] = random.choice(vis_cfg.pregunta("p3").opciones_ids())

    # Atribución de fricción - P1 es nominal, leer opciones del YAML
    atr_opciones = [opt["id"] for opt in yaml_data["dimensiones"]["atribucion_friccion"]["preguntas"]["p1"]["opciones"]]
    respuestas["atr_p1"] = random.choice(atr_opciones)
    # Si P1 = "no_sabria", P2 y P3 no se usan (se asignan 0 en scoring)
    if respuestas["atr_p1"] != "no_sabria":
        atr_cfg = cfg.dimension("atribucion_friccion")
        respuestas["atr_p2"] = random.choice(atr_cfg.pregunta("p2").opciones_ids())
        respuestas["atr_p3"] = random.choice(atr_cfg.pregunta("p3").opciones_ids())
    else:
        respuestas["atr_p2"] = "sin_evidencia"
        respuestas["atr_p3"] = "nunca"

    # Auto-cuantificación
    auto_cfg = cfg.dimension("auto_cuantificacion")
    unidad = random.choice(["mw", "kw"])
    capacidad_base = random.choice([1.0, 5.0, 10.0, 50.0, 100.0, 500.0])
    if unidad == "kw":
        capacidad_base = capacidad_base * 1000
    
    # P2 debe ser <= P1 (80-95% de P1 para realismo)
    pct_usable = random.uniform(0.80, 0.95)
    respuestas["auto_p1_capacidad"] = round(capacidad_base, 2)
    respuestas["auto_p2_capacidad"] = round(capacidad_base * pct_usable, 2)
    respuestas["auto_unidad"] = unidad
    respuestas["auto_p3"] = random.choice(auto_cfg.pregunta("p3").opciones_ids())

    # Bloqueantes
    blk_cfg = cfg.dimension("bloqueantes")
    bloqueantes_opts = ["presupuesto", "autoridad_politica", "herramientas", "personal", "nada"]
    # 70% tiene al menos 1 bloqueante, 30% dice "nada"
    if random.random() < 0.30:
        respuestas["blk_p1"] = ["nada"]
        respuestas["blk_p2"] = "no_bloqueante"
    else:
        n_bloqueantes = random.choice([1, 2, 3])
        respuestas["blk_p1"] = random.sample(bloqueantes_opts[:4], n_bloqueantes)
        respuestas["blk_p2"] = random.choice(["moderado", "fuerte", "estructural"])

    return {
        "operator_id": str(uuid.uuid4()),
        "source": "public_synthetic",
        "region": region,
        "facility_size": facility_size,
        "dc_type": dc_type,
        "benchmark_version": cfg.version,
        "dimension_version": cfg.version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **respuestas,
    }


def generar_dataset_csv(n_registros: int, force: bool = False) -> Path:
    """
    Genera el CSV con n_registros sintéticos usando faker.
    Si ya existe y force=False, no lo sobrescribe.
    """
    if DATASET_CSV_PATH.exists() and not force:
        print(f"CSV ya existe: {DATASET_CSV_PATH}")
        return DATASET_CSV_PATH

    print(f"Generando {n_registros} registros sintéticos con faker...")
    faker = Faker()
    faker.seed_instance(42)  # Reproducibilidad
    random.seed(42)

    cfg = get_config()
    
    # Cargar YAML directamente para opciones nominales
    yaml_path = Path(__file__).parent / "dimensiones.yaml"
    with open(yaml_path, encoding="utf-8") as f:
        yaml_data = yaml.safe_load(f)
    
    registros = [generar_registro_sintetico(faker, cfg, yaml_data) for _ in range(n_registros)]

    # Obtener todos los campos posibles (orden consistente)
    campos = list(registros[0].keys())

    with open(DATASET_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(registros)

    print(f"CSV generado: {DATASET_CSV_PATH} ({n_registros} registros)")
    return DATASET_CSV_PATH


# ── Carga en base de datos ───────────────────────────────────────────────────────

def cargar_csv_en_bd(csv_path: Path, force: bool = False) -> int:
    """
    Lee el CSV y carga las filas en operators + dimension_scores.
    Si ya hay datos con source="public_synthetic" y force=False, no los duplica.
    Retorna el número de registros cargados.
    """
    # Crear tablas si no existen
    Base.metadata.create_all(get_engine())

    cfg = get_config()
    registros_cargados = 0

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        filas = list(reader)

    with get_session() as session:
        # Verificar si ya hay datos públicos
        existentes = session.query(Operator).filter_by(source=SourceEnum.public_synthetic).count()
        if existentes > 0 and not force:
            print(f"Ya existen {existentes} registros con source='public_synthetic'")
            print("Usa --force para sobrescribir")
            return existentes

        if force and existentes > 0:
            print(f"Eliminando {existentes} registros existentes...")
            session.query(Operator).filter_by(source=SourceEnum.public_synthetic).delete()
            session.commit()

        print(f"Cargando {len(filas)} registros en la base de datos...")
        
        for fila in filas:
            operator_id = fila["operator_id"]
            
            # Crear operator
            op = Operator(
                id=operator_id,
                source=SourceEnum.public_synthetic,
                region=fila["region"],
                facility_size=fila["facility_size"],
                dc_type=fila["dc_type"],
                benchmark_version=fila["benchmark_version"],
                dimension_version=fila["dimension_version"],
                created_at=datetime.fromisoformat(fila["created_at"]),
            )
            session.add(op)

            # Calcular scores y crear dimension_scores (5 filas por operador)
            # Usamos el scoring engine para calcular los scores
            from app.engines.scoring_engine import ScoringEngine
            from app.schemas.request import CuestionarioRequest

            # Construir el request sintético
            try:
                req = construir_request_sintetico(fila)
                scoring_result = ScoringEngine().score(req)
                
                for score_detalle in scoring_result.scores:
                    session.add(DimensionScore(
                        operator_id=operator_id,
                        dimension=DimensionEnum(score_detalle.dimension),
                        score=score_detalle.score,
                        raw_answers=score_detalle.raw_answers,
                    ))
            except Exception as e:
                print(f"Error calculando scores para {operator_id}: {e}")
                # Scores dummy como fallback
                for dim in DimensionEnum:
                    session.add(DimensionScore(
                        operator_id=operator_id,
                        dimension=dim,
                        score=random.uniform(30, 90),
                        raw_answers={},
                    ))

            registros_cargados += 1
            
            # Commit cada 100 registros para no saturar memoria
            if registros_cargados % 100 == 0:
                session.commit()
                print(f"  {registros_cargados}/{len(filas)}...")

        session.commit()

    print(f"Total cargados: {registros_cargados} registros")
    return registros_cargados


def parse_lista_bloqueantes(valor: str) -> list:
    """Parsea una lista de bloqueantes desde el CSV (puede venir como string '[...]' o lista)."""
    if isinstance(valor, list):
        return valor
    if isinstance(valor, str):
        # El CSV guarda las listas como strings literales
        try:
            import ast
            return ast.literal_eval(valor)
        except:
            # Fallback: split por comas si falla literal_eval
            return [v.strip() for v in valor.replace("[", "").replace("]", "").split(",") if v.strip()]
    return []


def construir_request_sintetico(fila: dict) -> CuestionarioRequest:
    """Construye un CuestionarioRequest desde una fila del CSV."""
    from app.schemas.request import (
        ContextoOperador,
        CuestionarioRequest,
        RespuestasAtribucion,
        RespuestasAutoCuantificacion,
        RespuestasBloqueantes,
        RespuestasLatencia,
        RespuestasVisibilidad,
    )

    return CuestionarioRequest(
        contexto=ContextoOperador(
            facility_size=fila["facility_size"],
            region=fila["region"],
            dc_type=fila["dc_type"],
        ),
        latencia=RespuestasLatencia(
            p1_minutos=float(fila["lat_p1_minutos"]),
            p2_minutos=float(fila["lat_p2_minutos"]),
            p3=fila["lat_p3"],
        ),
        visibilidad=RespuestasVisibilidad(
            p1_sistemas=int(fila["vis_p1_sistemas"]),
            p2=fila["vis_p2"],
            p3=fila["vis_p3"],
        ),
        atribucion_friccion=RespuestasAtribucion(
            p1=fila["atr_p1"],
            p2=fila["atr_p2"],
            p3=fila["atr_p3"],
        ),
        auto_cuantificacion=RespuestasAutoCuantificacion(
            p1_capacidad_total=float(fila["auto_p1_capacidad"]),
            p2_capacidad_utilizable=float(fila["auto_p2_capacidad"]),
            unidad=fila["auto_unidad"],
            p3=fila["auto_p3"],
        ),
        bloqueantes=RespuestasBloqueantes(
            p1_bloqueantes=parse_lista_bloqueantes(fila["blk_p1"]),
            p2_severidad=fila["blk_p2"],
        ),
    )


# ── CLI ───────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Seed del dataset público sintético")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Sobrescribir CSV y datos existentes en BD",
    )
    parser.add_argument(
        "--n-registros",
        type=int,
        default=DEFAULT_N_REGISTROS,
        help=f"Número de registros a generar (default: {DEFAULT_N_REGISTROS})",
    )
    parser.add_argument(
        "--csv-only",
        action="store_true",
        help="Solo generar el CSV, no cargar en BD",
    )
    args = parser.parse_args()

    # Generar CSV
    csv_path = generar_dataset_csv(args.n_registros, args.force)

    if not args.csv_only:
        # Cargar en BD
        cargar_csv_en_bd(csv_path, args.force)
    else:
        print("CSV generado. Usa sin --csv-only para cargar en la base de datos.")


if __name__ == "__main__":
    main()
