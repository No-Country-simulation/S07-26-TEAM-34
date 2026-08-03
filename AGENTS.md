# Instrucciones del agente — Benchmark de Data Centers

## Fuente de verdad operativa
Trabajar siempre contra `.kiro/specs/benchmark-core/` (requirements, design, tasks).
Los docs largos en `docs/` son referencia: consultarlos solo cuando la tarea lo requiera.

## Orden de autoridad
1. Spec activa (requirements → design → tasks)
2. ADRs vigentes en `docs/adr/`
3. Políticas de privacidad y gobernanza
4. Documentación de arquitectura (`docs/`)
5. Contratos de API y output
6. Tareas de implementación

No modificar una decisión de nivel superior de forma silenciosa.

## Reglas no negociables (resumen)
Ver `.kiro/steering/core-rules.md` — cargado automáticamente en cada sesión.

## Forma de trabajar
1. Leer la tarea en `tasks.md` y las decisiones de diseño relevantes en `design.md`
2. Identificar entradas, salidas, invariantes y errores esperados
3. Consultar el ADR o doc específico solo si la tarea lo necesita
4. Implementar el cambio más pequeño que satisfaga la tarea
5. Ejecutar pruebas unitarias, de propiedades e integración aplicables
6. Actualizar `tasks.md` y documentación si cambia alguna decisión

## Límites del agente
- No inventar datos públicos ni prácticas del cuartil superior
- No publicar metodología sin backtest y aprobación humana
- No ampliar alcance con features no requeridas por la spec
- No usar texto generado por LLM como fuente estadística

## Steering files disponibles
- `core-rules.md` — siempre activo, reglas no negociables y motores
- `privacy.md` — carga cuando la tarea toca privacidad, agregación o cohortes
- `rebalancing.md` — carga cuando la tarea toca rebalanceo, snapshots o pesos
