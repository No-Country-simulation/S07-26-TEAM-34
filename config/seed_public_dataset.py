"""
Seed del dataset público sintético (backlog §11, §12 paso 2).

Carga config/dataset_publico_sintetico.csv (1000 filas calibradas contra
fuentes públicas de la industria) en las tablas operators y dimension_scores
con source="public_synthetic".

El CSV ya trae los scores por dimensión precalculados — este script
NO regenera datos ni recalcula scores, solo los persiste tal cual.

Uso:
    python config/seed_public_dataset.py
    python config/seed_public_dataset.py --force   # sobrescribe registros existentes
"""
from __future__ import annotations

import argparse
import csv
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.loader import get_config
from app.models.database import Base, get_engine, get_session
from app.models.tables import DimensionEnum, DimensionScore, Operator, SourceEnum

DATASET_CSV_PATH = Path(__file__).parent / "dataset_publico_sintetico.csv"


def _fila_a_raw_answers(fila: dict, campos: list[str]) -> dict:
    return {campo: fila[campo] for campo in campos if fila.get(campo) not in (None, "")}


def cargar_csv_en_bd(csv_path: Path, force: bool = False) -> int:
    Base.metadata.create_all(get_engine())
    cfg = get_config()

    with open(csv_path, encoding="utf-8") as f:
        filas = list(csv.DictReader(f))

    with get_session() as session:
        existentes = session.query(Operator).filter_by(source=SourceEnum.public_synthetic).count()
        if existentes > 0 and not force:
            print(f"Ya existen {existentes} registros con source='public_synthetic'")
            print("Usa --force para sobrescribir")
            return existentes

        if force and existentes > 0:
            print(f"Eliminando {existentes} registros existentes...")
            # Borrar en orden por FK
            session.query(DimensionScore).filter(
                DimensionScore.operator_id.in_(
                    session.query(Operator.id).filter_by(source=SourceEnum.public_synthetic)
                )
            ).delete(synchronize_session=False)
            session.query(Operator).filter_by(source=SourceEnum.public_synthetic).delete()
            session.commit()

        print(f"Cargando {len(filas)} registros...")
        cargados = 0

        for fila in filas:
            operator_id = fila.get("operator_id") or str(uuid.uuid4())

            session.add(Operator(
                id=operator_id,
                source=SourceEnum.public_synthetic,
                region=fila.get("region", ""),
                facility_size=fila.get("tamano_facility", ""),
                dc_type=fila.get("tipo_data_center", "").lower(),
                benchmark_version=cfg.version,
                dimension_version=cfg.version,
                created_at=datetime.now(timezone.utc),
            ))

            session.add(DimensionScore(
                operator_id=operator_id,
                dimension=DimensionEnum.latencia,
                score=float(fila["lat_score"]),
                raw_answers=_fila_a_raw_answers(
                    fila, ["lat_p1_minutos_cooling", "lat_p2_minutos_energia", "lat_p3_automatizacion"]
                ),
            ))
            session.add(DimensionScore(
                operator_id=operator_id,
                dimension=DimensionEnum.visibilidad,
                score=float(fila["vis_score"]),
                raw_answers=_fila_a_raw_answers(
                    fila, ["vis_p1_cantidad_sistemas", "vis_p2_frecuencia_consolidacion",
                           "vis_p3_acceso_vista_unificada"]
                ),
            ))
            session.add(DimensionScore(
                operator_id=operator_id,
                dimension=DimensionEnum.atribucion_friccion,
                score=float(fila["atr_score"]),
                raw_answers=_fila_a_raw_answers(
                    fila, ["atr_p1_interfaz", "atr_p2_respaldo", "atr_p3_vigencia"]
                ),
            ))
            session.add(DimensionScore(
                operator_id=operator_id,
                dimension=DimensionEnum.auto_cuantificacion,
                score=float(fila["auto_score"]),
                raw_answers=_fila_a_raw_answers(
                    fila, ["auto_p1_capacidad_instalada_mw", "auto_p2_capacidad_utilizable_mw",
                           "auto_pct_varada_calculado", "auto_p3_frecuencia_remedicion"]
                ),
            ))
            session.add(DimensionScore(
                operator_id=operator_id,
                dimension=DimensionEnum.bloqueantes,
                score=float(fila["blk_score"]),
                raw_answers=_fila_a_raw_answers(
                    fila, ["blk_p1_seleccionados", "blk_p1_cantidad", "blk_p2_severidad"]
                ),
            ))

            cargados += 1
            if cargados % 100 == 0:
                session.commit()
                print(f"  {cargados}/{len(filas)}...")

        session.commit()

    print(f"Total cargados: {cargados} registros")
    return cargados


def main():
    if not DATASET_CSV_PATH.exists():
        print(f"CSV no encontrado: {DATASET_CSV_PATH}")
        print("Genera primero el dataset con: python config/generar_dataset_publico.py")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Seed del dataset público sintético")
    parser.add_argument("--force", action="store_true",
                        help="Sobrescribir datos existentes en BD")
    args = parser.parse_args()

    print(f"CSV encontrado: {DATASET_CSV_PATH}")
    cargar_csv_en_bd(DATASET_CSV_PATH, args.force)


if __name__ == "__main__":
    main()
