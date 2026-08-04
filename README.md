# Datacenter Maturity Benchmark

Motor backend de un benchmark de madurez para data centers: mide coordinación entre energía, cooling y workload en 5 dimensiones, calcula percentiles contra un dataset público/primario con rebalanceo dinámico, y genera un diagnóstico personalizado por operador.

Proyecto de simulación laboral — No Country.

## Documentación

- [Marco Metodológico](docs/Documento_Metodologico_Benchmark.md) — las 5 dimensiones del benchmark: preguntas, normalización, fórmulas y calibración de mercado.
- [Backlog Definitivo](docs/Backlog_Definitivo_v3.md) — motores en scope, arquitectura, stack tecnológico y esquema de base de datos.

## Configuración

- [`config/questionnaire.yaml`](config/questionnaire.yaml) — fuente única de verdad de preguntas, opciones y scores.
- [`config/dataset_publico_sintetico.csv`](config/dataset_publico_sintetico.csv) — dataset público inicial (simulado, ver documento metodológico sección 2.7).
- [`config/generar_dataset_publico.py`](config/generar_dataset_publico.py) — script que genera el dataset sintético.

## Estructura del proyecto

```
app/
├── api/            # routers
├── schemas/        # esquemas de Pydantic
├── models/         # modelos de base de datos
├── engines/        # lógica de cálculo
├── repositories/   # acceso a base de datos
├── services/       # orquestación
└── prompts/        # plantillas de prompt del LLM

tests/
config/
docs/
```

## Stack

Python + FastAPI + Pydantic · PostgreSQL (Docker, Neon) · Next.js (Vercel) · pytest

Ver detalle completo en el [Backlog Definitivo](docs/Backlog_Definitivo_v3.md), sección 10.
