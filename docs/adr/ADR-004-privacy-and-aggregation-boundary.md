# ADR-004: Privacidad y agregación como frontera arquitectónica

- Estado: Aceptado
- Fecha: 2026-08-03

## Contexto

Aunque el diagnóstico sea “anónimo”, combinaciones de región, capacidad, tipo y workload pueden identificar a un operador.

## Decisión

Separar contacto opcional de respuestas; pseudonimizar; convertir cuasi-identificadores en bandas; aplicar umbrales y supresión antes de generar agregados o comparaciones.

## Consecuencias

- Menor riesgo de exposición.
- Algunas cohortes deberán generalizarse.
- El output debe explicar el fallback sin revelar información sensible.
