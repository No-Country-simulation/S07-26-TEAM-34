# Changelog de implementación — Benchmark de Madurez para Data Centers

> Documento interno. Registra qué existía antes, qué se cambió, por qué y cómo.
> Cubre toda la historia del proyecto desde el commit inicial hasta el estado actual en `develop`.

---

## Índice

1. [Estado inicial del repositorio](#1-estado-inicial)
2. [Fase Kiro — implementación completa MVP (master)](#2-fase-kiro)
3. [Tanda 1 — Infraestructura base (PRs 1-4)](#3-tanda-1)
4. [Tanda 2 — Motores y orquestador (PRs 5-10)](#4-tanda-2)
5. [Correcciones guía Diego (correcciones-guia-diego)](#5-correcciones-diego)
6. [Estado final del proyecto](#6-estado-final)
7. [Estructura de archivos](#7-estructura)
8. [Cómo levantar el servidor](#8-levantar)

---

## 1. Estado inicial del repositorio

**Commit**: `0a6747b` — "Estructura inicial: documentacion, config y esqueleto de carpetas"

El repositorio llegó con:

- Documentación de arquitectura en `docs/` (10 archivos MD + 10 ADRs)
- `Documento_Metodologico_Benchmark.md` — marco metodológico con 5 dimensiones, fórmulas exactas, escalas de score
- `Backlog_V3.md` — backlog definitivo con 7 motores, 3 tablas de DB, orden de desarrollo
- `Guia_PRs_Migracion.md` — plan de 11 PRs en 2 tandas
- **Sin código Python**. Sin tablas de DB. Sin tests.

### Lo que definía el estado inicial

**5 dimensiones** (Documento_Metodologico_Benchmark.md):
- Latencia de coordinación (P1/P2 numéricos en minutos, P3 categórico)
- Visibilidad cross-layer (P1 numérico en sistemas, P2/P3 categóricos)
- Atribución de fricción (P1 nominal, P2/P3 ordinales — fórmula sin P1)
- Auto-cuantificación (P1/P2 numéricos en MW/kW, completitud como score)
- Bloqueantes (P1 multi-selección nominal, score por cantidad)

**3 tablas de DB** (Backlog_V3.md §11):
- `operators` — una fila por cuestionario
- `dimension_scores` — 5 filas por operador
- `results` — resultado calculado, sin recalcular en cada request

**7 motores** (Backlog_V3.md §3):
- Scoring, Grupos comparables, Rebalanceo, Benchmark/percentiles, Top 25%, Interpretación, Privacidad

---

## 2. Fase Kiro — implementación completa MVP

**Commit**: `27e0bb2` — "feat: implementación completa MVP benchmark de madurez para data centers"
**Rama**: `master`

### Qué se construyó

Una implementación completa pero **sobredimensionada** respecto al backlog. Kiro construyó el sistema desde cero con arquitectura de enterprise: 9 tablas de DB, Alembic, 5 zonas de privacidad, jobs offline, panel admin, monitor de drift, flujo de aprobación LLM. Todo funcionaba y tenía 66 tests pasando.

**Estructura creada**:
```
src/benchmark/         ← implementación principal (legacy, luego eliminada)
  api/                 ← FastAPI con endpoints admin y públicos
  application/         ← orquestador process_response.py
  config/              ← loader de YAML versionado
  db/                  ← 9 tablas SQLAlchemy + Alembic + repository
  domain/              ← modelos de dominio Pydantic
  engines/             ← 8 motores incluyendo snapshot_builder, llm_interpretation
  jobs/                ← build_snapshot.py (job offline), methodology_update.py
  monitoring/          ← dashboard.py, drift_monitor.py
.kiro/                 ← specs, steering files, tasks.md
docs/                  ← arquitectura completa, ADRs
config/methodology/    ← YAML versionado con cuestionario ficticio
alembic/               ← migraciones de DB
```

### Por qué estaba sobredimensionado

Comparado con Backlog_V3.md:

| Lo que pedía el backlog | Lo que Kiro construyó |
|---|---|
| Motor de validación: FUERA DE SCOPE | `engines/validation.py` completo con quality score |
| Privacidad liviana: solo UUID | 5 zonas, ContactStore, supresión, auditoría completa |
| 3 tablas de DB | 9 tablas + Alembic |
| Sin panel admin | Panel admin con 9 endpoints, monitor de drift |
| Sin job offline | `build_snapshot.py` con backtest automático |
| Snapshots no pedidos | Sistema de snapshots inmutables con publicación atómica |

### Problemas metodológicos detectados luego

Las preguntas del cuestionario YAML no coincidían con el Documento_Metodologico_Benchmark.md:
- P1/P2 de Latencia debían ser inputs numéricos (minutos) — el YAML tenía opciones categóricas
- P1/P2 de Auto-cuantificación debían ser MW/kW numéricos — el YAML tenía categóricos
- P1 de Bloqueantes debía ser multi-selección — el modelo solo soportaba una opción
- La fórmula de rebalanceo implementada (media geométrica de 5 factores) era distinta a la del documento
- Las bandas de segmentación no coincidían con el documento

---

## 3. Tanda 1 — Infraestructura base

**Commits**: `7767391` → `a4b8791` | **Ramas**: `pr01` → `pr04` → `develop`

### Decisión de diseño

Se creó `develop` desde `master` y se empezó a construir la arquitectura correcta en `app/` siguiendo el Backlog_V3.md. La implementación legacy en `src/benchmark/` quedó en el repo (no se eliminó en esta tanda).

### PR 01 — Modelo de datos (`pr01-modelo-datos`)

**Antes**: no existía ninguna tabla de DB en `app/`.

**Después**: `app/models/tables.py` con exactamente las 3 tablas del backlog §11:

```python
class Operator(Base):      # operators — una fila por cuestionario
class DimensionScore(Base):# dimension_scores — 5 filas por operador
class Result(Base):        # results — resultado calculado
```

**Cómo**: SQLAlchemy con `Base.metadata.create_all()` (sin Alembic). Enums `SourceEnum` y `DimensionEnum` con validación en `@validates` para que SQLite también rechace valores inválidos. FKs con `ondelete="CASCADE"`. Timestamps con timezone.

**Tests**: 17 tests en `tests/models/test_tables.py` — creación, inserción, enums inválidos, FK, cascade delete.

---

### PR 02 — Schemas Pydantic (`pr02-schemas-pydantic`)

**Antes**: no existían schemas de entrada/salida.

**Después**:
- `config/dimensiones.yaml` — primer YAML de cuestionario (luego reemplazado)
- `app/schemas/request.py` — `CuestionarioRequest` con validación por dimensión
- `app/schemas/response.py` — `ResultadoResponse`, `PDFInputResponse`

**Decisiones**:
- P1/P2 de Latencia como `float ge=0` (minutos)
- P1 de Visibilidad como `int ge=0` (cantidad de sistemas)
- P1/P2 de Auto-cuantificación como `float | None` con validador `P2 <= P1`
- P1 de Bloqueantes como `list[BloqueanteTipo]` con min_length=1 (multi-selección)
- Caso borde "nada" en Bloqueantes: si solo `["nada"]`, `p2_severidad` no requerido
- `region` como `str` libre (no Literal) — doc §8 dice no cerrar para preservar anonimato

**Tests**: 26 tests en `tests/schemas/test_request.py`.

---

### PR 03 + 04 — FastAPI + Orquestador (`pr03-fastapi`)

**Antes**: no existía API ni orquestador en `app/`.

**Después**:
- `main.py` (raíz) — punto de entrada FastAPI
- `app/api/routers.py` — 3 endpoints: `POST /respuestas`, `GET /resultados/{id}`, `GET /resultados/{id}/pdf`
- `app/services/benchmark_service.py` — orquestador con 7 placeholders en orden del backlog §8

**Principio**: el orquestador no importa FastAPI, no sabe de HTTP. Los routers solo reciben y delegan.

**Orden de motores** (backlog §8):
```
scoring → grupos_comparables → rebalanceo → benchmark → top_quartile → interpretacion → privacidad
```

**Tests**: 19 tests — API (202/422/404), orquestador (orden, propagación de excepciones, UUID).

---

## 4. Tanda 2 — Motores y orquestador completo

**Commits**: `6fb21a5` → `2563a0c` | **Ramas**: `pr05` → `pr10` → `develop`

### PR 05 — Loader de YAML (`pr05-yaml-loader`)

**Antes**: no existía loader en `app/config/`.

**Después**: `app/config/loader.py` con `get_config()` cacheado (`lru_cache`).

**Cómo**: lee `config/dimensiones.yaml`, parsea buckets para variables numéricas, opciones categóricas y score por cantidad para bloqueantes. Resuelve la ruta en runtime (no en import time) para permitir override con `DIMENSIONES_YAML`. Detecta preguntas nominales (`es_nominal`) y numéricas (`es_numerico`).

**Tests**: 31 tests verificando scores exactos contra los valores del Documento_Metodologico_Benchmark.md — buckets de latencia (5/60/240/1440 min), escala 5 niveles de visibilidad (100/75/50/25/0), escala 3 niveles de atribución.

---

### PR 06 — Motor de scoring (`pr06-scoring-engine`)

**Antes**: placeholder devolvía `50.0` para todas las dimensiones.

**Después**: `app/engines/scoring_engine.py` con las 5 fórmulas exactas del documento:

| Dimensión | Fórmula |
|---|---|
| Latencia | `(score_p1 + score_p2 + score_p3) / 3` |
| Visibilidad | `(score_p1 + score_p2 + score_p3) / 3` |
| Atribución | `(score_p2 + score_p3) / 2` — P1 nominal excluida |
| Auto-cuantificación | `(score_completitud_p1p2 + score_p3) / 2` |
| Bloqueantes | `(score_cantidad_p1 + score_p2) / 2` |

**Casos borde implementados**:
- `p1 == "no_sabria"` en Atribución → P2 y P3 forzados a 0
- `P2 > P1` o valores `None` en Auto-cuantificación → `score_completitud = 0`
- Solo `["nada"]` en Bloqueantes → `score_cantidad = 100`, `sp2 = 100`
- `% capacidad varada = (P1 - P2) / P1 × 100` almacenado en `raw_answers`

**Tests**: 24 tests incluyendo monotonicidad, determinismo, límites de bucket (5 vs 6 minutos), evidencias.

---

### PR 07 — Motor de rebalanceo (`pr07-rebalanceo`)

**Antes**: placeholder ponía `peso_primario = 0` y usaba dataset sintético en memoria.

**Después**: `app/engines/rebalance_engine.py` con la fórmula exacta del documento §9:

```
peso_primario = (n_valido / (n_valido + k)) × factor_diversidad
k = 50  (constante de suavizado)
factor_diversidad = categorias_cubiertas / total_posibles
```

**Con n=50, k=50, diversidad=1.0 → peso≈50%. Con n=200 → peso≈80%.**

**Distribución combinada**: muestreo proporcional con `random.choices()`. Conectó el scoring engine real al orquestador (reemplazó el placeholder de PR 4).

**Tests**: 14 tests — invariante pesos suman 1, caso borde sin datos, monotonía, factor diversidad.

---

### PR 08 — Motor benchmark y percentiles (`pr08-benchmark-percentiles`)

**Antes**: placeholder devolvía percentil 50 para todo.

**Después**: `app/engines/benchmark_engine.py`. Calcula percentil del operador sobre la distribución combinada. Estadística robusta: mediana y cuartiles (p25/p50/p75), no promedio. Interpolación lineal para el percentil.

**Tests**: 11 tests — percentil en [0,100], score máximo → percentil alto, p25 < mediana < p75, sin distribución → neutral.

---

### PR 09 — Top quartile + Interpretación (`pr09-top-quartile-interpretacion`)

**Top quartile** (`app/engines/top_quartile_engine.py`): compara percentiles del operador con el umbral p75. Si `percentil >= 75` → sin brecha. Si no → brecha con descripción específica que menciona score y umbral.

**Interpretación** (`app/engines/interpretation_engine.py`):
- Perfil por regla determinística (umbrales sobre scores, no LLM)
- Fallback determinista cuando LLM no disponible
- Prompts en `app/prompts/diagnostico.txt` separados del código (backlog §7)

**Tests**: 5 + 8 = 13 tests.

---

### PR 10 — Privacidad + Persistencia + Orquestador completo (`pr10-privacidad-persistencia`)

**Antes**: orquestador con placeholders, sin persistencia real.

**Después**:
- `app/engines/privacy_engine.py` — genera UUID v4 aleatorio (privacidad liviana del backlog §3.7)
- `app/repositories/benchmark_repository.py` — `guardar_resultado()` en 3 tablas, `obtener_resultado()`
- `app/services/benchmark_service.py` — orquestador completo con todos los motores reales, lee dataset público/primario desde BD
- `tests/conftest.py` — crea tablas antes de tests de integración

**Tests de integración**: 13 tests verificando flujo completo — scores reales, percentiles, perfil, fricción, UUID, versiones registradas, casos mínimo/máximo.

**Total acumulado**: 234/234 tests pasando.

---

## 5. Correcciones guía Diego

**Commit**: `38040d0` | **Rama**: `correciones-guia-diego` → `develop`
**Fuente**: `Guia_Detallada_Backend_Diego.md` — documento con 14 correcciones identificadas en la rama `correcciones-criticas`.

### Contexto

Después de la Tanda 2, se detectaron 13 diferencias entre el código en `develop` y lo que necesitaba la integración con el frontend y Neon en producción. La guía documentó cada cambio necesario con el contenido exacto de cada archivo.

---

### Cambio 1 — `config/questionnaire.yaml` (nuevo archivo)

**Antes**: `config/dimensiones.yaml` con estructura propia (`tipo`, `opciones`, `id`).

**Después**: `config/questionnaire.yaml` con estructura canónica (`type`, `options`, `value`/`score`). Este es el archivo que el frontend consume directamente vía `GET /questionnaire`.

**Diferencias clave de estructura**:
```yaml
# Antes (dimensiones.yaml)           # Después (questionnaire.yaml)
tipo: "categorico_ordinal"           type: "categorical_ordinal"
opciones:                            options:
  - id: "automatizado"                 - value: "automatizado"
    value: 0                             score: 100

tipo: "numerico_minutos"             type: "numeric"
buckets:                             scoring:
  - max: 5                             buckets:
    score: 100                           - max_inclusive: 5
                                           score: 100
```

**IDs de dimensiones** cambian de cortos a largo+mapeo:
- `dimensiones.yaml`: `latencia`, `visibilidad`, etc.
- `questionnaire.yaml`: `latencia_coordinacion`, `visibilidad_cross_layer`, etc. → mapeados a cortos en el loader

---

### Cambio 2 — `app/config/loader.py` reescrito

**Antes**: leía `config/dimensiones.yaml`, var de entorno `DIMENSIONES_YAML`.

**Después**: lee `config/questionnaire.yaml`, var de entorno `QUESTIONNAIRE_YAML`.

**Cambios técnicos**:
- Nuevo mapeo `_DIMENSION_ID_MAP` para traducir IDs largos → cortos
- `_short_pregunta_id()` con regex para extraer `p1`/`p2`/`p3` del ID largo (ej. `lat_p1_minutos_cooling` → `p1`)
- `PreguntaConfig` parsea `type`/`options[value]`/`score` en vez de `tipo`/`opciones[id]`/`value`
- `SegmentacionConfig` recibe lista de dicts (no dict de dicts)
- `score_por_cantidad` para bloqueantes leído directamente del YAML

---

### Cambio 3 — `app/schemas/request.py` — Literals corregidos

**Por qué**: los valores no coincidían con los `value` del `questionnaire.yaml`, así que cualquier request desde el frontend habría fallado la validación Pydantic.

| Campo | Antes | Después |
|---|---|---|
| FacilitySize | `"menos_1mw"`, `"1_5mw"`, `"5_20mw"`, `"mas_20mw"` | `"<1MW"`, `"1-5MW"`, `"5-20MW"`, `">20MW"` |
| region | `Literal[...]` cerrado | `str` libre (doc §8: no cerrar por anonimato) |
| Latencia P3 | `"alertas_accion_manual"`, `"reporte_revision_manual"` | `"alertas_manual"`, `"reporte_periodico"` |
| Visibilidad P2 | `"mensual"` | `"mensual_o_mas"` |
| Visibilidad P3 | `"cualquier_responsable"`, `"rol_especifico"` | `"cualquiera"`, `"un_rol"` |
| Atribución P1 | `"no_sabria"` | `"no_sabria_decir"` |
| Atribución P2 | `"con_evidencia"` | `"con_medicion"` |
| Atribución P3 | `"activamente"`, `"periodicamente"`, `"nunca"` | `"revision_activa"`, `"revision_periodica"`, `"nunca_revisada"` |
| Auto-cuant P3 | `"tiempo_real"`, `"nunca"` | `"continuamente"`, `"nunca_remedido"` |
| Bloqueantes P2 | `"no_bloqueante"` | `"no_es_real"` |

---

### Cambio 4 — `app/engines/scoring_engine.py` — caso borde

**Antes**: `if atr.p1 == "no_sabria":` → nunca se disparaba porque el valor correcto era `"no_sabria_decir"`.

**Después**: `if atr.p1 == "no_sabria_decir":` — el caso borde ahora funciona.

---

### Cambio 5 — `app/engines/rebalance_engine.py` — seed fijo

**Antes**: `random.choices()` con el módulo global → distribuciones distintas en cada ejecución.

**Después**: `random.Random(_SEED)` con `_SEED = 42` → mismos inputs = misma distribución = tests deterministas.

---

### Cambio 6 — `app/engines/interpretation_engine.py` — firma extendida

**Antes**: `interpretar(scores, benchmark, top_quartile)` — sin contexto del operador.

**Después**: `interpretar(scores, benchmark, top_quartile, raw_answers=None, contexto=None)`.

**Nuevo en el motor**:
- `_INTERFAZ_FRICCION_LABELS` — traduce IDs a texto legible para el prompt
- `_BLOQUEANTE_LABELS` — ídem para bloqueantes
- El prompt recibe ahora: interfaz de fricción, bloqueantes reportados y capacidad instalada vs. utilizable

---

### Cambio 7 — `app/prompts/diagnostico.txt` — prompt mejorado

**Antes**: prompt básico que solo recibía perfil, fricción, scores y brechas → el LLM generaba una versión en prosa de números que el operador ya veía.

**Después**: prompt con instrucción de razonamiento socrático ("esto sugiere", "es consistente con") y 3 señales diagnósticas adicionales que no entran al score:
- Interfaz donde el operador percibe mayor pérdida de capacidad
- Bloqueantes reportados
- Capacidad instalada vs. utilizable

---

### Cambio 8 — `app/services/benchmark_service.py`

**Antes**: `scores_primarios=[]` hardcodeado → el rebalanceo siempre tenía peso_primario=0 sin importar cuántas respuestas reales hubiera acumuladas.

**Después**:
- `_cargar_scores_por_source(source)` — consulta real a DB filtrando por `source`
- `_contar_categorias_cubiertas_primarias()` — cuenta combinaciones distintas para `factor_diversidad`
- `obtener_resultado(operator_id)` — método nuevo para que el endpoint GET funcione

---

### Cambio 9 — `app/api/routers.py`

**Antes**: `GET /resultados/{id}` y `GET /resultados/{id}/pdf` eran stubs con `raise HTTPException(404)` hardcodeado.

**Después**:
- `GET /questionnaire` — nuevo endpoint que sirve el YAML al frontend
- Los dos GET ahora llaman a `_service.obtener_resultado()` y `_service.pdf_input()`
- `_construir_llm_client()` — instancia `GeminiClient` si `GEMINI_API_KEY` está seteada; si no, fallback determinista

---

### Cambio 10 — `main.py` → `app/main.py`

**Antes**: `main.py` en la raíz sin CORS.

**Después**: `app/main.py` con `CORSMiddleware(allow_origins=["*"])`. Comando de inicio cambió de `uvicorn main:app` a `uvicorn app.main:app`.

**Por qué el CORS importaba**: sin CORS, el navegador bloqueaba cualquier request desde el frontend en otro dominio. Además, los errores de Neon (conexión caída por inactividad) se reportaban como errores de CORS porque nunca llegaba una respuesta HTTP real.

---

### Cambio 11 — `app/engines/llm_clients/gemini_client.py`

**Antes**: no había implementación real de cliente LLM. `BenchmarkService()` siempre se creaba con `llm_client=None`.

**Después**: `GeminiClient` con `google-genai`. Se instancia solo si `GEMINI_API_KEY` está disponible. Implementa el `Protocol LLMClient` con método `generar(prompt) -> str`.

---

### Cambio 12 — `pyproject.toml`

**Antes**: `pydantic==2.7.4`, `httpx==0.27.0`, sin `google-genai`.

**Después**: `pydantic==2.9.2`, `httpx==0.28.1`, `google-genai==2.2.0`. Se eliminaron `alembic`, `scipy` y `numpy` (sin uso en `app/`).

**Por qué**: `google-genai` requiere `httpx>=0.28.1` y `pydantic>=2.9.0`. Sin actualizar estas versiones, `pip install` fallaba con `ResolutionImpossible` en cualquier entorno limpio.

---

### Cambio 13 — `.gitignore`

**Antes**: `lib/` sin barra inicial → Git ignoraba cualquier carpeta `lib` en cualquier nivel, incluyendo `frontend/src/lib/`.

**Después**: `/lib/` con barra inicial → solo ignora `lib/` en la raíz.

**Impacto real**: `frontend/src/lib/formState.ts` (lógica de estado del formulario) nunca se había subido a git. Vercel clonaba sin ese archivo → build fallaba con `Cannot find module '../../lib/formState'`.

---

### Actualización de tests tras los cambios

Se actualizaron 6 archivos de tests para usar los nuevos Literal values:
- `tests/config/test_loader.py` — nueva variable de entorno `QUESTIONNAIRE_YAML`, nuevos values
- `tests/schemas/test_request.py` — payloads con nuevos Literals
- `tests/engines/test_scoring_engine.py` — payloads con nuevos Literals
- `tests/services/test_benchmark_service.py` — payloads con nuevos Literals
- `tests/services/test_benchmark_service_integrado.py` — payloads y `from app.main import app`
- `tests/api/test_routers.py` — payloads y `from app.main import app`

**Resultado**: 246/246 tests pasando.

---

## 6. Estado final del proyecto

**Tests**: 246/246 pasando
**Rama activa**: `develop`
**Último commit**: `38040d0`

### Lo que funciona hoy

- Pipeline completo: `POST /api/v1/respuestas` → 5 scores reales → percentiles → fricción → diagnóstico → persistido en DB
- `GET /api/v1/questionnaire` → YAML del cuestionario para el frontend
- `GET /api/v1/resultados/{id}` → resultado desde DB (sin recalcular)
- `GET /api/v1/resultados/{id}/pdf` → payload para PDF
- `GET /health` → Render health check
- LLM Gemini opcional — si no hay API key, fallback determinista
- CORS configurado para integración con frontend

### Lo que queda pendiente según el backlog

- **Dataset público sintético** (`config/dataset_publico_sintetico.csv`): el backlog dice "ya generado", pero el CSV con 1.000 filas calibradas contra fuentes reales no está en el repo. El script `config/seed_public_dataset.py` está listo para cargarlo cuando exista.
- **Motor de grupos comparables** (backlog §3.2): implementado como placeholder `grupo = "global"`. Falta segmentar por region/facility_size/dc_type cuando haya dataset primario.
- **Render + Neon en producción**: documentado en `Guia_Detallada_Backend_Diego.md` §14. Requiere variables de entorno `DATABASE_URL` y opcionalmente `GEMINI_API_KEY`.

---

## 7. Estructura de archivos

```
app/
├── __init__.py
├── main.py                          ← punto de entrada (uvicorn app.main:app)
├── api/
│   ├── routers.py                   ← 4 endpoints: questionnaire, respuestas, resultados, pdf
├── config/
│   ├── loader.py                    ← lee config/questionnaire.yaml, cacheado
├── engines/
│   ├── scoring_engine.py            ← 5 dimensiones, fórmulas exactas del doc metodológico
│   ├── rebalance_engine.py          ← peso_primario = (n_valido/(n_valido+k)) × factor_diversidad
│   ├── benchmark_engine.py          ← percentiles por interpolación, estadística robusta
│   ├── top_quartile_engine.py       ← brechas vs. cuartil superior
│   ├── interpretation_engine.py     ← perfil determinístico + LLM opcional
│   ├── privacy_engine.py            ← UUID v4 aleatorio (privacidad liviana)
│   └── llm_clients/
│       └── gemini_client.py         ← adaptador Gemini (requiere GEMINI_API_KEY)
├── models/
│   ├── database.py                  ← SQLAlchemy engine, get_session(), create_tables()
│   └── tables.py                    ← 3 tablas: Operator, DimensionScore, Result
├── prompts/
│   └── diagnostico.txt              ← template del prompt LLM (backlog §7)
├── repositories/
│   └── benchmark_repository.py      ← guardar_resultado(), obtener_resultado()
├── schemas/
│   ├── request.py                   ← CuestionarioRequest con validación por dimensión
│   └── response.py                  ← ResultadoResponse, PDFInputResponse
└── services/
    └── benchmark_service.py         ← orquestador principal

config/
├── questionnaire.yaml               ← fuente única de preguntas, opciones y scores
└── seed_public_dataset.py           ← carga dataset_publico_sintetico.csv en DB

tests/
├── conftest.py                      ← crea tablas antes de tests de integración
├── models/test_tables.py            ← 17 tests — DB
├── schemas/test_request.py          ← 26 tests — validación Pydantic
├── config/test_loader.py            ← 31 tests — scores exactos del doc metodológico
├── api/test_routers.py              ← 10 tests — HTTP
├── services/
│   ├── test_benchmark_service.py    ← 19 tests — orquestador
│   └── test_benchmark_service_integrado.py  ← 13 tests — flujo completo
└── engines/
    ├── test_scoring_engine.py       ← 24 tests
    ├── test_rebalance_engine.py     ← 14 tests
    ├── test_benchmark_engine.py     ← 11 tests
    ├── test_top_quartile_engine.py  ← 5 tests
    ├── test_interpretation_engine.py← 8 tests
    └── test_privacy_engine.py       ← 3 tests
```

---

## 8. Cómo levantar el servidor

### Desarrollo local (SQLite)

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest tests/           # 246 tests
.venv/bin/uvicorn app.main:app --reload
```

### Producción (Neon + Render)

Variables de entorno necesarias:
```
DATABASE_URL=postgresql://user:pass@host/dbname   # Neon
GEMINI_API_KEY=...                                 # opcional — sin ella usa fallback
```

Comando de inicio (Render):
```
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Cargar dataset público (cuando esté disponible)

```bash
python config/seed_public_dataset.py              # carga config/dataset_publico_sintetico.csv
python config/seed_public_dataset.py --force      # sobrescribe datos existentes
```

---

*Documento generado el 2026-08-11. Refleja el estado del commit `38040d0` en `develop`.*
