# Benchmark de madurez operativa — Data Centers

Motor de benchmark que convierte respuestas anónimas de operadores de data centers en scores por dimensión, percentiles y un diagnóstico personalizado.

## Qué hace

```
Operador responde cuestionario (5 dimensiones)
    ↓
Scores determinísticos (0-100 por dimensión)
    ↓
Posición relativa en el grupo comparable
    ↓
Brechas con el cuartil superior
    ↓
Diagnóstico personalizado (reglas + LLM opcional)
    ↓
Resultado guardado de forma anónima
```

Las 5 dimensiones miden **madurez de coordinación cross-layer** (energía, cooling, workload):
1. **Latencia de coordinación** — qué tan rápido reacciona el sistema ante cambios
2. **Visibilidad cross-layer** — si existe una vista unificada de las tres capas
3. **Atribución de fricción** — dónde se pierde capacidad y con qué evidencia
4. **Auto-cuantificación** — si el operador puede medir su stranded capacity
5. **Bloqueantes** — qué impide resolver los problemas identificados

## Levantar en desarrollo

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# Cargar dataset público sintético (referencia inicial)
.venv/bin/python config/seed_public_dataset.py

# Levantar la API
.venv/bin/uvicorn app.main:app --reload
```

La API queda disponible en `http://localhost:8000`. Documentación interactiva en `http://localhost:8000/docs`.

## Correr tests

```bash
.venv/bin/pytest tests/
```

## Variables de entorno

Copiar `.env.example` a `.env` y completar:

| Variable | Requerida | Descripción |
|---|---|---|
| `DATABASE_URL` | En producción | URL de PostgreSQL (Neon). Sin ella usa SQLite local. |
| `GEMINI_API_KEY` | No | API key de Gemini para diagnósticos con LLM. Sin ella usa fallback determinista. |

## Deploy en Render

El archivo `render.yaml` contiene la configuración completa. Las variables `DATABASE_URL` y `GEMINI_API_KEY` se configuran manualmente en el dashboard de Render.

Comando de inicio: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

## Endpoints principales

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/v1/questionnaire` | Cuestionario para el frontend |
| `POST` | `/api/v1/respuestas` | Procesa una respuesta y devuelve el diagnóstico |
| `GET` | `/api/v1/resultados/{id}` | Recupera un resultado ya calculado |
| `GET` | `/api/v1/resultados/{id}/pdf` | Payload para generación de PDF |
| `GET` | `/health` | Health check (Render) |

## Estructura del proyecto

```
app/
├── main.py                  # Punto de entrada FastAPI + CORS
├── api/routers.py           # Endpoints
├── config/loader.py         # Lee config/questionnaire.yaml
├── engines/                 # 7 motores de cálculo determinístico
├── models/                  # 3 tablas SQLAlchemy
├── repositories/            # Acceso a DB
├── schemas/                 # Validación Pydantic entrada/salida
├── services/                # Orquestador del pipeline
└── prompts/diagnostico.txt  # Template del prompt LLM

config/
├── questionnaire.yaml              # Fuente única de preguntas y scores
├── dataset_publico_sintetico.csv   # 1.000 filas de referencia (sintético)
├── generar_dataset_publico.py      # Regenera el CSV si hace falta
└── seed_public_dataset.py          # Carga el CSV en la DB
```

## Notas metodológicas

- El LLM **nunca calcula scores, percentiles ni elige el perfil** — solo redacta texto
- El dataset inicial es **sintético**, calibrado contra reportes públicos de la industria (Uptime Institute, Gartner). No son datos de operadores reales
- Los percentiles mejoran a medida que se acumulan respuestas primarias (rebalanceo dinámico)
- Ver `Documento_Metodologico_Benchmark.md` para el marco metodológico completo
- Ver `Backlog_Definitivo_v3.md` para el alcance del MVP
