# ADR-009: Metodología declarativa y versionada

- Estado: Aceptado
- Fecha: 2026-08-03

## Contexto

Reglas ocultas en código o prompts dificultan revisión, auditoría y cambios controlados.

## Decisión

Preguntas, opciones, scores, pesos, cohortes, privacidad y parámetros de rebalanceo se definen en configuración o tablas versionadas y validadas al publicar.

## Consecuencias

- Mejor revisión y trazabilidad.
- Se requiere un proceso de migración y validación de configuración.
- El código implementa mecanismos; la configuración define la metodología publicada.
