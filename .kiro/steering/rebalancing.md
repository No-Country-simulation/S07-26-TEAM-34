---
inclusion: fileMatch
fileMatchPattern: "**/rebalanc*,**/snapshot*,**/weight*,**/offline*"
---

# Rebalanceo dinámico — guía de implementación

## Principio
Empieza 100% evidencia pública. El peso primario crece solo cuando la evidencia primaria es madura. El peso se calcula **por dimensión y cohorte**, nunca como ratio global.

## Cinco factores (normalizados 0–1)
- **Suficiencia** — tamaño efectivo vs. mínimo objetivo
- **Calidad** — promedio ponderado de quality scores y completitud
- **Representatividad** — cobertura de segmentos esperados, sin concentración excesiva
- **Actualidad** — decaimiento por edad de respuestas
- **Estabilidad** — variación entre ventanas o bootstraps

## Combinación
Media geométrica o producto penalizado de los 5 factores. Un factor débil no queda oculto por otros fuertes. Resultado = peso primario; complemento = peso público.

## Invariantes obligatorios
- Sin datos primarios válidos → peso primario = 0
- peso_público + peso_primario = 1
- Máximo cambio de peso entre snapshots definido en config versionada
- Un resultado ya emitido nunca se recalcula por cambio de pesos

## Snapshot candidato almacena
factores calculados · pesos por dimensión/cohorte · datos de entrada · versión de parámetros · métricas de estabilidad · motivo de aprobación/rechazo

## Salvaguardas
- Alerta ante saltos de percentiles por segmento
- Rechazo automático si se degrada privacidad o estabilidad
- Fallback a última versión aprobada si falla la construcción
- Reporte de drift entre fuentes públicas y primarias

## Referencia completa
`docs/03_DYNAMIC_REBALANCING.md` · ADR-005 · ADR-002 · ADR-010
