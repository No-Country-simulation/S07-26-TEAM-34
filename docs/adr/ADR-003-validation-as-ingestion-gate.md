# ADR-003: Validación como compuerta de ingreso

- Estado: Aceptado
- Fecha: 2026-08-03

## Contexto

Respuestas incompletas, contradictorias, duplicadas o sospechosas pueden degradar scores y dataset.

## Decisión

Ejecutar validación antes de scoring y antes de incorporación al dataset primario. La salida incluirá estado, errores, advertencias y quality score. Solo respuestas elegibles contribuyen al benchmark.

## Consecuencias

- Mejor calidad y trazabilidad.
- Se necesita separar error bloqueante de advertencia.
- El quality score puede contribuir al tamaño efectivo y rebalanceo.
