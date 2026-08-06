"""
Genera el dataset publico sintetico inicial del benchmark.

Calibrado de forma aproximada con fuentes publicas reales (Uptime Institute
Global Data Center Survey 2025/2026, EkkoSense, Sunbird DCIM, Gartner,
Capgemini, Dataversity, Ivanti - ver Documento_Metodologico_Benchmark.md).

Este dataset es SIMULADO. Las filas representan simulaciones calibradas,
NO 1000 operadores reales -- no hay "mil data centers" detras de este
numero, hay mil combinaciones de respuestas generadas siguiendo una
distribucion que el equipo definio a partir de reportes publicos.
Se usa unicamente como base de comparacion publica inicial mientras no
existen suficientes respuestas primarias reales (ver Motor de rebalanceo,
seccion 9 del documento metodologico).
"""

import csv
import random

N_FILAS = 1000
SEED = 42

random.seed(SEED)

REGIONES = ["Norteamerica", "Europa", "Asia-Pacifico", "Latinoamerica", "Medio Oriente/Africa"]
TAMANOS = ["<1MW", "1-5MW", "5-20MW", ">20MW"]
TIPOS = ["Hyperscale", "Colocation", "Enterprise", "Edge"]


def elegir_ponderado(opciones, pesos):
    return random.choices(opciones, weights=pesos, k=1)[0]


# ---------------------------------------------------------------------------
# Dimension 1: Latencia de coordinacion
# ---------------------------------------------------------------------------
BUCKETS_MINUTOS = [
    (0, 5, 100),
    (6, 60, 75),
    (61, 240, 50),
    (241, 1440, 25),
    (1441, 4320, 0),
]
PESOS_LATENCIA_MINUTOS = [0.05, 0.15, 0.25, 0.35, 0.20]

AUTOMATIZACION_OPCIONES = [
    ("Automatizado, sin intervencion humana", 100),
    ("Alertas automaticas, accion manual", 67),
    ("Reporte periodico + revision manual", 33),
    ("No hay proceso definido", 0),
]
PESOS_AUTOMATIZACION = [0.10, 0.20, 0.30, 0.40]


def generar_minutos_y_score():
    lo, hi, score = random.choices(BUCKETS_MINUTOS, weights=PESOS_LATENCIA_MINUTOS, k=1)[0]
    minutos = random.randint(lo, hi)
    return minutos, score


def generar_latencia():
    min_cooling, score_p1 = generar_minutos_y_score()
    min_energia, score_p2 = generar_minutos_y_score()
    idx = random.choices(range(4), weights=PESOS_AUTOMATIZACION, k=1)[0]
    automatizacion, score_p3 = AUTOMATIZACION_OPCIONES[idx]
    score = round((score_p1 + score_p2 + score_p3) / 3, 2)
    return {
        "lat_p1_minutos_cooling": min_cooling,
        "lat_p2_minutos_energia": min_energia,
        "lat_p3_automatizacion": automatizacion,
        "lat_score": score,
    }


# ---------------------------------------------------------------------------
# Dimension 2: Visibilidad cross-layer
# ---------------------------------------------------------------------------
SISTEMAS_OPCIONES = [(1, 100), (2, 67), (3, 33), (4, 0)]  # 4 = "mas de 3"
PESOS_SISTEMAS = [0.10, 0.25, 0.40, 0.25]

FRECUENCIA_CONSOLIDACION = [
    ("Tiempo real / continuo", 100),
    ("Diario", 75),
    ("Semanal", 50),
    ("Mensual o mas espaciado", 25),
    ("Nunca se cruza la informacion", 0),
]
PESOS_FRECUENCIA = [0.05, 0.15, 0.25, 0.30, 0.25]

ACCESO_VISTA = [
    ("Cualquier responsable puede verlas juntas", 100),
    ("Solo un rol consolida manualmente", 50),
    ("Cada equipo ve solo su capa", 0),
]
PESOS_ACCESO = [0.15, 0.35, 0.50]


def generar_visibilidad():
    n_sistemas, score_p1 = random.choices(SISTEMAS_OPCIONES, weights=PESOS_SISTEMAS, k=1)[0]
    idx2 = random.choices(range(5), weights=PESOS_FRECUENCIA, k=1)[0]
    frecuencia, score_p2 = FRECUENCIA_CONSOLIDACION[idx2]
    idx3 = random.choices(range(3), weights=PESOS_ACCESO, k=1)[0]
    acceso, score_p3 = ACCESO_VISTA[idx3]
    score = round((score_p1 + score_p2 + score_p3) / 3, 2)
    return {
        "vis_p1_cantidad_sistemas": n_sistemas,
        "vis_p2_frecuencia_consolidacion": frecuencia,
        "vis_p3_acceso_vista_unificada": acceso,
        "vis_score": score,
    }


# ---------------------------------------------------------------------------
# Dimension 3: Atribucion de friccion
# ---------------------------------------------------------------------------
INTERFACES = ["Energia<->Cooling", "Cooling<->Workload", "Workload<->Energia", "No sabria decir"]
PESOS_INTERFACES = [0.40, 0.20, 0.30, 0.10]

RESPALDO_OPCIONES = [
    ("Si, con reporte o medicion concreta", 100),
    ("Solo estimacion aproximada, sin registro formal", 50),
    ("No, es una apreciacion sin evidencia registrada", 0),
]
PESOS_RESPALDO = [0.15, 0.40, 0.45]

VIGENCIA_OPCIONES = [
    ("Se revisa activamente con cada cambio relevante", 100),
    ("Se revisa periodicamente (ej. anual)", 50),
    ("Nunca se reviso desde la percepcion inicial", 0),
]
PESOS_VIGENCIA = [0.20, 0.35, 0.45]


def generar_atribucion():
    interfaz = random.choices(INTERFACES, weights=PESOS_INTERFACES, k=1)[0]
    if interfaz == "No sabria decir":
        respaldo, score_p2 = "No aplica", 0
        vigencia, score_p3 = "No aplica", 0
    else:
        idx2 = random.choices(range(3), weights=PESOS_RESPALDO, k=1)[0]
        respaldo, score_p2 = RESPALDO_OPCIONES[idx2]
        idx3 = random.choices(range(3), weights=PESOS_VIGENCIA, k=1)[0]
        vigencia, score_p3 = VIGENCIA_OPCIONES[idx3]
    score = round((score_p2 + score_p3) / 2, 2)
    return {
        "atr_p1_interfaz": interfaz,
        "atr_p2_respaldo": respaldo,
        "atr_p3_vigencia": vigencia,
        "atr_score": score,
    }


# ---------------------------------------------------------------------------
# Dimension 4: Auto-cuantificacion
# ---------------------------------------------------------------------------
PROB_PROVEE_NUMEROS = 0.25  # probabilidad de completar P1/P2 de forma coherente

FRECUENCIA_REMEDICION = [
    ("Continuamente / en tiempo real", 100),
    ("Trimestral o semestral", 67),
    ("Anual", 33),
    ("Nunca se remidio", 0),
]
PESOS_FRECUENCIA_REMEDICION = [0.10, 0.20, 0.25, 0.45]


def generar_auto_cuantificacion():
    provee = random.random() < PROB_PROVEE_NUMEROS
    if provee:
        capacidad_instalada = round(random.uniform(2, 60), 2)  # MW
        # stranded real ~20-25% segun Uptime Institute, con dispersion
        pct_varada = max(0.0, min(0.60, random.gauss(0.225, 0.08)))
        capacidad_utilizable = round(capacidad_instalada * (1 - pct_varada), 2)
        score_completitud = 100
        pct_varada_calculado = round((capacidad_instalada - capacidad_utilizable) / capacidad_instalada * 100, 2)
    else:
        capacidad_instalada = None
        capacidad_utilizable = None
        score_completitud = 0
        pct_varada_calculado = None

    idx = random.choices(range(4), weights=PESOS_FRECUENCIA_REMEDICION, k=1)[0]
    frecuencia, score_p3 = FRECUENCIA_REMEDICION[idx]

    score = round((score_completitud + score_p3) / 2, 2)
    return {
        "auto_p1_capacidad_instalada_mw": capacidad_instalada,
        "auto_p2_capacidad_utilizable_mw": capacidad_utilizable,
        "auto_pct_varada_calculado": pct_varada_calculado,
        "auto_p3_frecuencia_remedicion": frecuencia,
        "auto_score": score,
    }


# ---------------------------------------------------------------------------
# Dimension 5: Bloqueantes
# ---------------------------------------------------------------------------
BLOQUEANTES_PROB = {
    "Presupuesto": 0.55,
    "Falta de autoridad/politica interna": 0.40,
    "Falta de herramientas tecnicas": 0.30,
    "Falta de personal capacitado": 0.30,
}

SEVERIDAD_OPCIONES = [
    ("No es un bloqueante real", 100),
    ("Obstaculo moderado, resoluble con esfuerzo", 67),
    ("Obstaculo fuerte, poco probable en el corto plazo", 33),
    ("Bloqueante estructural", 0),
]
PESOS_SEVERIDAD = [0.05, 0.30, 0.40, 0.25]


def generar_bloqueantes():
    seleccionados = [nombre for nombre, p in BLOQUEANTES_PROB.items() if random.random() < p]
    cantidad = len(seleccionados)
    if cantidad == 0:
        seleccionados = ["Nada, podriamos resolverlo"]
        score_cantidad = 100
        severidad, score_p2 = "No es un bloqueante real", 100
    else:
        if cantidad == 1:
            score_cantidad = 67
        elif cantidad == 2:
            score_cantidad = 33
        else:
            score_cantidad = 0
        idx = random.choices(range(4), weights=PESOS_SEVERIDAD, k=1)[0]
        severidad, score_p2 = SEVERIDAD_OPCIONES[idx]

    score = round((score_cantidad + score_p2) / 2, 2)
    return {
        "blk_p1_seleccionados": "; ".join(seleccionados),
        "blk_p1_cantidad": cantidad if seleccionados != ["Nada, podriamos resolverlo"] else 0,
        "blk_p2_severidad": severidad,
        "blk_score": score,
    }


# ---------------------------------------------------------------------------
# Generacion completa
# ---------------------------------------------------------------------------
def generar_operador(op_id):
    fila = {
        "operator_id": f"SYN-{op_id:05d}",
        "region": random.choice(REGIONES),
        "tamano_facility": random.choice(TAMANOS),
        "tipo_data_center": random.choice(TIPOS),
    }
    fila.update(generar_latencia())
    fila.update(generar_visibilidad())
    fila.update(generar_atribucion())
    fila.update(generar_auto_cuantificacion())
    fila.update(generar_bloqueantes())
    return fila


def main():
    filas = [generar_operador(i) for i in range(1, N_FILAS + 1)]
    columnas = list(filas[0].keys())

    salida = "dataset_publico_sintetico.csv"
    with open(salida, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columnas)
        writer.writeheader()
        writer.writerows(filas)

    # resumen rapido para validar que los promedios calzan con lo documentado
    promedios = {}
    for dim in ["lat_score", "vis_score", "atr_score", "auto_score", "blk_score"]:
        valores = [f[dim] for f in filas]
        promedios[dim] = round(sum(valores) / len(valores), 2)

    print(f"Generadas {N_FILAS} filas en {salida}")
    print("Promedios por dimension (para validar contra el documento metodologico):")
    for dim, prom in promedios.items():
        print(f"  {dim}: {prom}")


if __name__ == "__main__":
    main()
