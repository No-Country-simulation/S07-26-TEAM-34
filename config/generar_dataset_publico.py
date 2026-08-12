"""
Genera config/dataset_publico_sintetico.csv

1.000 filas sintéticas calibradas contra fuentes públicas reales:
  - Uptime Institute Global DC Survey 2025/2026: PUE promedio 1.54, estancado 6 años
  - Uptime Institute: 45% de incidentes por causas de energía
  - EkkoSense / Sunbird DCIM: 20-40% de capacidad desperdiciada
  - Gartner: 75% de infraestructura necesitará visibilidad en tiempo real para 2027

Las distribuciones se sesgan hacia scores bajos-medios para reflejar que
la fragmentación y coordinación manual son la norma, no la excepción.

NUNCA se commitea con datos reales de operadores.
Este CSV es simulado y debe etiquetarse como tal en cualquier output al usuario.

Uso:
    python config/generar_dataset_publico.py
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

random.seed(2024)

OUTPUT_PATH = Path(__file__).parent / "dataset_publico_sintetico.csv"

# ── Distribuciones calibradas por dimensión ───────────────────────────────────
# Pares (score, peso_relativo) — refleja reportes de industria

# Latencia: media ~35/100 (mayoría reactiva, doc §3 calibración)
LATENCIA_DIST = [
    (0,   15),   # > 1 día o sin proceso — más común de lo esperado
    (11,  20),   # mezcla baja automatización
    (22,  15),
    (33,  20),   # reporte periódico manual
    (44,  10),
    (56,   8),
    (67,   7),   # alertas automáticas
    (78,   3),
    (89,   1),
    (100,  1),   # automatizado completo — solo líderes del sector
]

# Visibilidad: media ~30/100 (Gartner: mayoría aún no tiene herramientas unificadas)
VISIBILIDAD_DIST = [
    (0,   20),
    (11,  18),
    (22,  17),
    (33,  15),   # consolidación semanal / 3 sistemas
    (44,  10),
    (56,   8),
    (67,   6),
    (78,   4),
    (89,   1),
    (100,  1),
]

# Atribución: media ~35/100 (falta de evidencia es la norma)
ATRIBUCION_DIST = [
    (0,   25),   # sin evidencia, nunca revisado
    (17,  20),
    (33,  18),
    (50,  15),   # estimación, revisión periódica
    (67,  10),
    (83,   8),
    (100,  4),
]

# Auto-cuantificación: media ~20/100 (Uptime: mayoría no sabe cuánta capacidad tiene varada)
AUTO_CUANT_DIST = [
    (0,   40),   # sin P1/P2 coherentes o nunca remedido
    (17,  20),
    (33,  15),
    (50,  12),
    (67,   7),
    (83,   4),
    (100,  2),
]

# Bloqueantes: media ~40/100 (presupuesto y silos son barreras frecuentes — Capgemini, Dataversity)
BLOQUEANTES_DIST = [
    (0,   10),
    (17,  12),
    (33,  20),
    (50,  22),
    (67,  18),
    (83,  12),
    (100,  6),
]

REGIONES = ["LATAM", "North America", "Europe", "Asia-Pacific", "Other"]
REGION_WEIGHTS = [20, 30, 25, 20, 5]

TAMANIOS = ["<1MW", "1-5MW", "5-20MW", ">20MW"]
TAMANIO_WEIGHTS = [15, 35, 35, 15]

TIPOS = ["hyperscale", "colocation", "enterprise", "edge"]
TIPO_WEIGHTS = [15, 30, 45, 10]

# Respuestas categóricas (labels del cuestionario, no value-ids)
LAT_P3_OPTIONS = [
    ("Automatizado, sin intervención humana", 100),
    ("Alertas automáticas, acción manual", 67),
    ("Reporte periódico + revisión manual", 33),
    ("No hay proceso definido", 0),
]
LAT_P3_WEIGHTS = [8, 25, 35, 32]

VIS_P2_OPTIONS = [
    ("Tiempo real / continuo", 100),
    ("Diario", 75),
    ("Semanal", 50),
    ("Mensual o más espaciado", 25),
    ("Nunca se cruza la información", 0),
]
VIS_P2_WEIGHTS = [5, 15, 25, 30, 25]

VIS_P3_OPTIONS = [
    ("Cualquier responsable puede verlas juntas en un solo lugar", 100),
    ("Solo un rol específico las consolida manualmente para reportar", 50),
    ("Cada equipo ve solo su capa; nadie tiene la vista completa", 0),
]
VIS_P3_WEIGHTS = [15, 35, 50]

ATR_P1_OPTIONS = ["energia_cooling", "cooling_workload", "workload_energia", "no_sabria_decir"]
ATR_P1_WEIGHTS = [40, 20, 30, 10]

ATR_P2_OPTIONS = [
    ("Sí, con reporte o medición concreta", 100),
    ("Solo una estimación aproximada, sin registro formal", 50),
    ("No, es una apreciación sin evidencia registrada", 0),
]
ATR_P2_WEIGHTS = [20, 35, 45]

ATR_P3_OPTIONS = [
    ("Se revisa activamente con cada cambio relevante de infraestructura o workload", 100),
    ("Se revisa periódicamente (por ejemplo, anual)", 50),
    ("Nunca se revisó desde que se formó la percepción inicial", 0),
]
ATR_P3_WEIGHTS = [15, 30, 55]

BLK_P2_OPTIONS = [
    ("No es un bloqueante real, podríamos resolverlo si quisiéramos", 100),
    ("Obstáculo moderado, resoluble con esfuerzo", 67),
    ("Obstáculo fuerte, poco probable resolverlo en el corto plazo", 33),
    ("Bloqueante estructural, no lo vemos resoluble en el corto plazo", 0),
]
BLK_P2_WEIGHTS = [10, 30, 35, 25]


def _weighted_choice(options, weights):
    return random.choices(options, weights=weights, k=1)[0]


def _score_from_dist(dist):
    options = [d[0] for d in dist]
    weights = [d[1] for d in dist]
    base = _weighted_choice(options, weights)
    # Añadir variación continua ±8 puntos para evitar distribución escalonada
    jitter = random.uniform(-8, 8)
    return round(max(0.0, min(100.0, base + jitter)), 2)


def generar_fila(i: int) -> dict:
    region = _weighted_choice(REGIONES, REGION_WEIGHTS)
    tamano = _weighted_choice(TAMANIOS, TAMANIO_WEIGHTS)
    dc_type = _weighted_choice(TIPOS, TIPO_WEIGHTS)

    # Latencia
    lat_p1 = random.choices([2, 8, 30, 90, 300, 900, 2000],
                             weights=[5, 10, 20, 25, 20, 15, 5])[0]
    lat_p2 = random.choices([2, 8, 30, 90, 300, 900, 2000],
                             weights=[5, 10, 20, 25, 20, 15, 5])[0]
    lat_p3_label, lat_p3_score = _weighted_choice(LAT_P3_OPTIONS, LAT_P3_WEIGHTS)

    def bucket_lat(m):
        if m <= 5:    return 100
        if m <= 60:   return 75
        if m <= 240:  return 50
        if m <= 1440: return 25
        return 0

    lat_score = round((bucket_lat(lat_p1) + bucket_lat(lat_p2) + lat_p3_score) / 3, 2)

    # Visibilidad
    vis_p1 = random.choices([1, 2, 3, 5], weights=[10, 25, 35, 30])[0]
    vis_p2_label, vis_p2_score = _weighted_choice(VIS_P2_OPTIONS, VIS_P2_WEIGHTS)
    vis_p3_label, vis_p3_score = _weighted_choice(VIS_P3_OPTIONS, VIS_P3_WEIGHTS)

    def bucket_vis(n):
        if n <= 1: return 100
        if n <= 2: return 67
        if n <= 3: return 33
        return 0

    vis_score = round((bucket_vis(vis_p1) + vis_p2_score + vis_p3_score) / 3, 2)

    # Atribución
    atr_p1 = _weighted_choice(ATR_P1_OPTIONS, ATR_P1_WEIGHTS)
    atr_p2_label, atr_p2_score = _weighted_choice(ATR_P2_OPTIONS, ATR_P2_WEIGHTS)
    atr_p3_label, atr_p3_score = _weighted_choice(ATR_P3_OPTIONS, ATR_P3_WEIGHTS)
    if atr_p1 == "no_sabria_decir":
        atr_p2_score = atr_p3_score = 0
    atr_score = round((atr_p2_score + atr_p3_score) / 2, 2)

    # Auto-cuantificación
    has_data = random.random() < 0.45  # 45% proveen datos coherentes
    if has_data:
        p1_cap = round(random.uniform(0.5, 80), 1)
        pct_varada = random.uniform(5, 50)
        p2_cap = round(p1_cap * (1 - pct_varada / 100), 1)
        score_completitud = 100
        pct_varada_calc = round(pct_varada, 2)
    else:
        p1_cap = p2_cap = None
        score_completitud = 0
        pct_varada_calc = None

    auto_p3_label, auto_p3_score = _weighted_choice(
        [("Continuamente / en tiempo real", 100),
         ("Trimestral o semestral", 67),
         ("Anual", 33),
         ("Nunca se remidió", 0)],
        [5, 15, 25, 55]
    )
    auto_score = round((score_completitud + auto_p3_score) / 2, 2)

    # Bloqueantes
    n_bloqueantes = random.choices([0, 1, 2, 3, 4], weights=[8, 30, 35, 20, 7])[0]
    blk_opciones = ["presupuesto", "autoridad_politica", "herramientas", "personal"]
    if n_bloqueantes == 0:
        blk_seleccionados = "nada"
        blk_cantidad = 0
        blk_score_cantidad = 100
    else:
        selected = random.sample(blk_opciones, min(n_bloqueantes, len(blk_opciones)))
        blk_seleccionados = "|".join(selected)
        blk_cantidad = len(selected)
        if blk_cantidad == 1: blk_score_cantidad = 67
        elif blk_cantidad == 2: blk_score_cantidad = 33
        else: blk_score_cantidad = 0

    blk_p2_label, blk_p2_score = _weighted_choice(BLK_P2_OPTIONS, BLK_P2_WEIGHTS)
    if n_bloqueantes == 0:
        blk_p2_score = 100
    blk_score = round((blk_score_cantidad + blk_p2_score) / 2, 2)

    return {
        "operator_id": f"synth_{i:05d}",
        "region": region,
        "tamano_facility": tamano,
        "tipo_data_center": dc_type,
        # Latencia
        "lat_p1_minutos_cooling": lat_p1,
        "lat_p2_minutos_energia": lat_p2,
        "lat_p3_automatizacion": lat_p3_label,
        "lat_score": lat_score,
        # Visibilidad
        "vis_p1_cantidad_sistemas": vis_p1,
        "vis_p2_frecuencia_consolidacion": vis_p2_label,
        "vis_p3_acceso_vista_unificada": vis_p3_label,
        "vis_score": vis_score,
        # Atribución
        "atr_p1_interfaz": atr_p1,
        "atr_p2_respaldo": atr_p2_label,
        "atr_p3_vigencia": atr_p3_label,
        "atr_score": atr_score,
        # Auto-cuantificación
        "auto_p1_capacidad_instalada_mw": p1_cap if p1_cap is not None else "",
        "auto_p2_capacidad_utilizable_mw": p2_cap if p2_cap is not None else "",
        "auto_pct_varada_calculado": pct_varada_calc if pct_varada_calc is not None else "",
        "auto_p3_frecuencia_remedicion": auto_p3_label,
        "auto_score": auto_score,
        # Bloqueantes
        "blk_p1_seleccionados": blk_seleccionados,
        "blk_p1_cantidad": blk_cantidad,
        "blk_p2_severidad": blk_p2_label,
        "blk_score": blk_score,
    }


def main():
    filas = [generar_fila(i) for i in range(1, 1001)]

    fieldnames = list(filas[0].keys())
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filas)

    # Estadísticas de validación
    scores = {dim: [] for dim in ["lat", "vis", "atr", "auto", "blk"]}
    for fila in filas:
        for dim in scores:
            scores[dim].append(float(fila[f"{dim}_score"]))

    print(f"Dataset generado: {OUTPUT_PATH}")
    print(f"Total filas: {len(filas)}")
    print("\nEstadísticas por dimensión (media / desv):")
    import statistics
    for dim, vals in scores.items():
        print(f"  {dim}: media={statistics.mean(vals):.1f} | "
              f"std={statistics.stdev(vals):.1f} | "
              f"min={min(vals):.1f} | max={max(vals):.1f}")


if __name__ == "__main__":
    main()
