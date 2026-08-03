# ADR-002: Snapshots publicados e inmutables

- Estado: Aceptado
- Fecha: 2026-08-03

## Contexto

El dataset cambia con cada respuesta. Calcular contra datos vivos haría que resultados iguales pudieran variar y dificultaría auditoría y soporte.

## Decisión

Cada resultado utilizará un snapshot publicado e inmutable. Los cambios de datos o metodología generan un snapshot candidato, backtest y nueva publicación.

## Consecuencias

- Reproducibilidad total.
- Publicación controlada y rollback simple.
- Existe una latencia entre recibir datos y reflejarlos en el benchmark.
- Se necesita almacenamiento y gobierno de versiones.
