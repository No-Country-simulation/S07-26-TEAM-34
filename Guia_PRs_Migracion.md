# Guía de PRs — Migración hacia el Backlog Definitivo

*Documento de trabajo para ir alineando la implementación actual con el [Backlog_Definitivo_v3.md](Backlog_Definitivo_v3.md) y el [Documento_Metodologico_Benchmark.md](Documento_Metodologico_Benchmark.md). Se avanza en tandas: la Tanda 1 se hace y se revisa antes de arrancar la Tanda 2 — no continuar sin aprobación explícita entre tandas.*

---

## Cómo usar este documento

Cada PR de acá abajo se puede pasar directo como base de un prompt a un asistente de código. La sección "Convenciones generales" aplica a **todos** los PRs, no solo al primero — conviene incluirla siempre en el prompt, no asumir que "ya se sabe".

**Ramas**: desde `main` nace `develop`. De `develop` nace una rama por cada PR de este documento, nombrada igual que el PR (`pr01-modelo-datos`, `pr02-schemas-pydantic`, etc.). Cada rama se abre como Pull Request contra `develop`, se revisa, se mergea, y ahí nace la siguiente. Cuando una tanda completa esté aprobada y funcionando, `develop` se mergea a `main`.

Antes de pedir revisión de un PR: correr los tests, confirmar que pasan, y completar el checklist del final de este documento.

---

## Convenciones generales (aplican a todos los PRs)

### Estructura de carpetas
Ver la estructura completa en [Backlog_Definitivo_v3.md](Backlog_Definitivo_v3.md), sección 9. Resumen de las carpetas principales: `api/` (routers), `schemas/` (Pydantic), `models/` (tablas de base de datos), `engines/` (cálculo puro), `repositories/` (acceso a base de datos), `services/` (orquestación), `prompts/` (plantillas del LLM), `config/questionnaire.yaml` (fuente única de preguntas/scores).

### Testing
- Los tests viven en `tests/`, con la misma estructura de carpetas que `app/`.
- Se corren con `pytest` desde la raíz del proyecto.
- Nombrar los tests de forma descriptiva: `test_<qué_se_prueba>_<escenario>_<resultado_esperado>`.
- Cada motor o pieza con lógica debe cubrir tres tipos de caso:
  1. **Caso normal**: input típico → output esperado.
  2. **Caso extremo/borde**: los documentados explícitamente (ej. P2 > P1 en Auto-cuantificación, "No sabría decir" en Atribución, "Nada podríamos resolverlo" en Bloqueantes, límites de los buckets de score como 5 vs. 6 minutos).
  3. **Caso inválido**: dato faltante, tipo incorrecto, valor fuera de rango.

### Nombre de cada PR
Igual al de la rama (`pr01-modelo-datos`, etc.), con una línea en la descripción indicando qué sección del backlog o del documento metodológico cubre.

---

## TANDA 1 — Infraestructura base

*No avanzar a la Tanda 2 hasta que esta tanda esté revisada y aprobada.*

### PR 1 — Modelo de datos

**Stack de esta pieza**: PostgreSQL, corriendo en un contenedor Docker, alojado en **Neon** (no Supabase, no Render free — ver backlog sección 10 para el porqué). **ORM: SQLAlchemy** (no estaba elegido explícitamente en ningún documento anterior — se define acá, por ser el estándar de facto con FastAPI). Sin Alembic — alcanza con `Base.metadata.create_all()` para este tamaño de esquema (3 tablas).

**Qué hacer**: crear exactamente estas 3 tablas (backlog, sección 11) — ninguna tabla adicional en este PR.

**Tabla `operators`** — una fila por cuestionario completado, sintético o real. Es la tabla que separa identidad de respuesta.

| Columna | Tipo | Nota |
|---|---|---|
| `id` | UUID (PK) | identificador aleatorio, sin relación con nombre/email/empresa |
| `source` | enum(`public_synthetic`, `primary`) | distingue el dataset público sintético de las respuestas reales |
| `region` | text | campo de contexto |
| `facility_size` | text | campo de contexto |
| `dc_type` | text | campo de contexto |
| `benchmark_version` | text | versión de `config/questionnaire.yaml` vigente al momento de la respuesta |
| `dimension_version` | text | ídem, por si se versiona distinto que el benchmark general |
| `created_at` | timestamp (con timezone) | |

**Tabla `dimension_scores`** — una fila por operador y por dimensión (5 filas por operador).

| Columna | Tipo | Nota |
|---|---|---|
| `id` | serial (PK) | |
| `operator_id` | UUID (FK → `operators.id`) | |
| `dimension` | enum(`visibilidad`, `atribucion_friccion`, `latencia`, `auto_cuantificacion`, `bloqueantes`) | |
| `score` | numeric(5,2) | 0-100, ya normalizado |
| `raw_answers` | jsonb | respuestas crudas de esa dimensión (minutos, categoría elegida, etc.) |

**Tabla `results`** — una fila por operador, el resultado ya calculado (evita recalcular todo cada vez que alguien vuelve a pedir su reporte).

| Columna | Tipo | Nota |
|---|---|---|
| `operator_id` | UUID (PK, FK → `operators.id`) | |
| `percentiles` | jsonb | percentil por dimensión, dentro de su grupo comparable |
| `friccion_principal` | text | dimensión con el percentil relativo más bajo |
| `profile` | text | perfil cualitativo (regla determinística, Motor de interpretación) |
| `top_quartile_gaps` | jsonb | brechas concretas contra el cuartil superior por dimensión |
| `diagnostico_texto` | text | texto redactado por el LLM |
| `computed_at` | timestamp (con timezone) | |

**No crear ninguna tabla más** — ni de auditoría, ni de contacto, ni de snapshots (ver backlog, sección 5, para la lista completa de lo que quedó fuera).

**Seed del dataset público**: además de crear las tablas, este PR incluye un script (`config/seed_public_dataset.py` o similar) que lee `config/dataset_publico_sintetico.csv` (ya está en el repo) y carga cada fila como una fila en `operators` (con `source="public_synthetic"`) + sus 5 filas correspondientes en `dimension_scores`. Sin este paso, las tablas quedan creadas pero vacías — el CSV no sirve de nada solo por estar en el repo, tiene que terminar insertado.

**Tests esperados** (`tests/models/`):
- Las 3 tablas se crean sin error.
- Insertar una fila válida en cada tabla funciona.
- Los campos tipo enum (`source` en `operators`, `dimension` en `dimension_scores`) rechazan valores fuera de la lista permitida.
- Insertar en `dimension_scores` o `results` con un `operator_id` que no existe en `operators` falla (integridad referencial).
- El script de seed carga las 1.000 filas del CSV correctamente (contar filas en `operators` con `source="public_synthetic"` después de correrlo, debe dar 1.000).

**Buenas prácticas puntuales**: columnas en snake_case, timestamps con timezone, UUID como tipo nativo (Postgres lo soporta).

---

### PR 2 — Esquemas de Pydantic

**Qué hacer**: 3 schemas — uno de entrada (`ResponseCreate`), uno de salida del resultado (`ResultOut`), y uno de salida del cuestionario (`QuestionnaireOut`). Basados campo por campo en `config/questionnaire.yaml` — no inventar ni renombrar ningún campo.

**`ResponseCreate`** (entrada de `POST /responses`) — 14 campos de respuesta + 3 de contexto:

| Campo | Tipo Pydantic | Restricción |
|---|---|---|
| `lat_p1_minutos_cooling` | `int` | `ge=0` |
| `lat_p2_minutos_energia` | `int` | `ge=0` |
| `lat_p3_automatizacion` | `Literal["automatizado","alertas_manual","reporte_periodico","sin_proceso"]` | — |
| `vis_p1_cantidad_sistemas` | `int` | `ge=0` |
| `vis_p2_frecuencia_consolidacion` | `Literal["tiempo_real","diario","semanal","mensual_o_mas","nunca"]` | — |
| `vis_p3_acceso_vista_unificada` | `Literal["cualquiera","un_rol","nadie"]` | — |
| `atr_p1_interfaz` | `Literal["energia_cooling","cooling_workload","workload_energia","no_sabria_decir"]` | — |
| `atr_p2_respaldo` | `Literal["con_medicion","estimacion","sin_evidencia"] \| None` | opcional — ver caso borde abajo |
| `atr_p3_vigencia` | `Literal["revision_activa","revision_periodica","nunca_revisada"] \| None` | opcional — ver caso borde abajo |
| `auto_p1_capacidad_instalada` | `float` | `gt=0` |
| `auto_p2_capacidad_utilizable` | `float` | `gt=0` |
| `auto_capacidad_unidad` | `Literal["MW","KW"]` | un único selector, aplica a P1 y P2 juntos |
| `auto_p3_frecuencia_remedicion` | `Literal["continuamente","trimestral_semestral","anual","nunca_remedido"]` | — |
| `blk_p1_seleccionados` | `list[Literal["presupuesto","autoridad_politica","herramientas","personal","nada"]]` | mínimo 1 elemento; si incluye `"nada"`, debe ser el único elemento (validador) |
| `blk_p2_severidad` | `Literal["no_es_real","moderado","fuerte","estructural"] \| None` | opcional — ver caso borde abajo |
| `facility_size` | `Literal["<1MW","1-5MW","5-20MW",">20MW"]` | — |
| `region` | `str` | sin lista fija en `questionnaire.yaml` — texto libre por ahora (marcar como pendiente si se quiere acotar a una lista) |
| `dc_type` | `Literal["hyperscale","colocation","enterprise","edge"]` | — |

**Casos borde a nivel de schema** (documento metodológico, casos borde por dimensión):
- Si `atr_p1_interfaz == "no_sabria_decir"`: `atr_p2_respaldo` y `atr_p3_vigencia` pueden venir en `None` — el motor de scoring les asigna 0, no el schema.
- Si `blk_p1_seleccionados == ["nada"]`: `blk_p2_severidad` puede venir en `None` — el motor le asigna 100, no el schema.
- **Importante**: `auto_p2_capacidad_utilizable > auto_p1_capacidad_instalada` (P2 > P1) **no se rechaza a nivel de schema** — es una validación de negocio que vive en el motor de scoring (el par se descarta del cálculo derivado y el score de completitud da 0), no un error 422 de la API.

**`ResultOut`** (salida de `GET /results/{operator_id}`):

| Campo | Tipo |
|---|---|
| `operator_id` | `UUID` |
| `percentiles` | `dict[str, float]` (clave = id de dimensión) |
| `friccion_principal` | `str` |
| `profile` | `str` |
| `top_quartile_gaps` | `dict[str, str]` |
| `diagnostico_texto` | `str` |

**`QuestionnaireOut`** (salida de `GET /questionnaire`): estructura de dimensiones/preguntas/opciones tal como está en `config/questionnaire.yaml` — se puede servir como `dict` leído directo del YAML, no hace falta tipar cada campo con Pydantic si el YAML ya es la fuente de verdad.

**Tests esperados** (`tests/schemas/`):
- Caso válido: un payload completo y correcto valida sin error.
- Caso inválido: falta un campo obligatorio, o un `Literal` con un valor fuera de la lista → falla con `ValidationError`.
- Casos límite: valores en el borde de los rangos numéricos (0 minutos, capacidad muy chica pero positiva).
- Caso borde: `atr_p1_interfaz="no_sabria_decir"` con `atr_p2`/`atr_p3` en `None` → valida sin error.
- Caso borde: `blk_p1_seleccionados=["nada"]` con `blk_p2_severidad=None` → valida sin error.
- Caso inválido específico: `blk_p1_seleccionados=["nada","presupuesto"]` (mezcla "nada" con otra opción) → falla.
- Confirmar que `auto_p2_capacidad_utilizable > auto_p1_capacidad_instalada` **no** falla a nivel de schema (es válido para Pydantic, aunque el motor lo trate distinto).

**Buenas prácticas puntuales**: los `Literal` del schema tienen que coincidir carácter por carácter con los `value` de `config/questionnaire.yaml` — cualquier diferencia de tipeo rompe la validación en silencio para el frontend.

---

### PR 3 — Instancia de FastAPI

**Qué hacer**: `main.py` solo crea la app, configura CORS y registra los routers de `api/`. Los 4 endpoints exactos (requerimientos técnicos para frontend), ninguno más:

| Método | Ruta | Request | Response | Notas |
|---|---|---|---|---|
| `GET` | `/questionnaire` | — | `QuestionnaireOut` | lee `config/questionnaire.yaml`, no toca la base de datos |
| `POST` | `/responses` | `ResponseCreate` | `{"operator_id": UUID, "status": "processed"}` | dispara el orquestador (PR 4) |
| `GET` | `/results/{operator_id}` | — | `ResultOut` | `404` si el `operator_id` no existe o el resultado todavía no está calculado |
| `GET` | `/pdf_input/{operator_id}` | — | mismo contenido que `ResultOut`, formato para Proyecto 5 | `404` con el mismo criterio que `/results` |

**CORS**: el frontend va a estar en un dominio de Vercel y el backend en Render — son orígenes distintos. Configurar `CORSMiddleware` permitiendo el dominio del frontend (aunque sea `*` de forma temporal en desarrollo, documentarlo como algo a acotar antes de producción).

**Tests esperados** (`tests/api/`):
- Con `TestClient`, cada uno de los 4 endpoints responde 200 con un payload/caso válido.
- `POST /responses` responde 422 con un payload inválido (falta un campo, o un valor fuera de los `Literal` permitidos).
- `GET /results/{operator_id}` y `GET /pdf_input/{operator_id}` responden 404 con un `operator_id` inexistente.
- La forma del JSON de cada respuesta tiene exactamente las claves de `ResultOut`/`QuestionnaireOut` — ni de más ni de menos.

**Buenas prácticas puntuales**: los routers no calculan nada — reciben, llaman al orquestador (`services/`), devuelven. Ningún router debería tener un `import` de `engines/` directamente — solo `services/`.

---

### PR 4 — Orquestador

**Qué hacer**: la función `process_response(answers, context)` que ejecuta, en este orden exacto (backlog, sección 8 — arquitectura del scope definitivo):

1. **Motor de privacidad (3.7)**: genera el `operator_id` (UUID aleatorio, sin relación con ningún dato identificable).
2. **Guardar en `operators`**: `id`, `source="primary"`, los 3 campos de contexto, `benchmark_version`/`dimension_version` (versión vigente de `config/questionnaire.yaml`), `created_at`.
3. **Motor de scoring (3.1)**: calcula el score de las 5 dimensiones a partir de `answers`.
4. **Guardar en `dimension_scores`**: una fila por dimensión (5 en total), con `score` y `raw_answers`.
5. **Motor de grupos comparables (3.2)**: determina el grupo comparable del operador (todavía no existe — placeholder que devuelve el grupo global).
6. **Motor de rebalanceo (3.3)**: calcula pesos y distribución combinada, por dimensión (todavía no existe — placeholder).
7. **Motor de benchmark y percentiles (3.4)**: percentil por dimensión (todavía no existe — placeholder).
8. **Motor de comparación top 25% (3.5)**: brechas contra el cuartil superior (todavía no existe — placeholder).
9. **Motor de interpretación (3.6)**: perfil (regla determinística) + texto redactado por el LLM, con guardrails (todavía no existe — placeholder).
10. **Guardar en `results`**: todo lo anterior, más `computed_at`.
11. **Devolver** `operator_id`.

Para los pasos 5 a 9, cuyos motores todavía no existen (llegan en la Tanda 2), usar una función placeholder que devuelva un valor fijo válido (ej. percentil 50, perfil `"pendiente"`) — así el orquestador completo se puede testear de punta a punta desde ahora, y cuando cada motor real llegue en su PR correspondiente, solo se reemplaza el placeholder por la llamada real, sin tocar el orden ni la estructura del orquestador.

**Tests esperados** (`tests/services/`):
- Llama a los 11 pasos en el orden exacto de arriba (se puede verificar con mocks que registran el orden de las llamadas).
- Guarda correctamente en `operators` antes de calcular cualquier score.
- Guarda correctamente en `dimension_scores` (5 filas) antes de pasar a grupos comparables.
- Si un motor lanza una excepción, no se traga en silencio — se propaga o se loguea explícitamente, y no queda una fila a medio guardar en `results`.

**Buenas prácticas puntuales**: el orquestador no importa FastAPI ni sabe nada de HTTP — solo recibe datos y devuelve datos, para poder testearlo sin levantar el servidor. No hace las consultas a la base de datos directamente — llama a `repositories/` para eso.

---

## TANDA 2 — Motores (a detallar y enviar después de aprobar la Tanda 1)

*Placeholder — se completa con el mismo formato (qué hacer / tests esperados / buenas prácticas) una vez que la Tanda 1 esté aprobada.*

- PR 5 — Cuestionario cargado desde `questionnaire.yaml` (ya provisto). *Nota: las preguntas, opciones y scores no van escritos a mano en un `.py` — se leen del YAML.*
- PR 6 — Motor de scoring. *Nota: el engine no importa FastAPI ni toca la base de datos directamente — recibe datos, devuelve datos.*
- PR 7 — Inputs numéricos de Latencia y Auto-cuantificación + cálculo de % de capacidad varada
- PR 8 — Multi-selección de Bloqueantes
- PR 9 — Fórmulas de índice por dimensión
- PR 10 — Motor de rebalanceo (fórmula del documento, calculada por dimensión)
- PR 11 — Bandas de segmentación

---

## Checklist antes de pedir revisión de cualquier PR

- [ ] Los tests corren y pasan (`pytest`).
- [ ] La descripción del PR dice qué sección del backlog/documento metodológico cubre.
- [ ] No se tocaron archivos fuera del alcance de este PR puntual.
- [ ] Ninguna pregunta, opción o score quedó escrita a mano en un `.py` — todo sale de `config/questionnaire.yaml`.
