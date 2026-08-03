# ADR-010: Separación entre procesamiento online y offline

- Estado: Aceptado
- Fecha: 2026-08-03

## Contexto

Construir distribuciones, agregados y backtests en cada request aumenta latencia, variabilidad y riesgo de concurrencia.

## Decisión

El flujo online usa un snapshot ya publicado. Los procesos de agregación, rebalanceo y construcción de snapshots se ejecutan offline y se publican de forma atómica.

## Consecuencias

- Respuesta rápida y reproducible.
- Requiere jobs, estados de snapshot y monitoreo.
- La incorporación al benchmark ocurre por lotes o ventanas controladas.
