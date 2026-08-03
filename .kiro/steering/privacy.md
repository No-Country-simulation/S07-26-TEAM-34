---
inclusion: fileMatch
fileMatchPattern: "**/privacy*,**/aggregat*,**/pseudon*,**/cohort*,**/suppress*"
---

# Privacidad y agregación — guía de implementación

## Cinco zonas (frontera dura entre ellas)
1. **Contacto opcional** — email separado, retención limitada, nunca entra a scoring
2. **Respuestas pseudónimas** — ID aleatorio, no derivado de datos del operador
3. **Analítica** — scores + bandas (cuasi-identificadores ya convertidos)
4. **Agregada** — solo métricas que superan umbral mínimo configurado
5. **Publicación** — snapshots y outputs sin datos individuales

## Reglas de implementación
- Cuasi-identificadores (capacidad exacta, localización, edad del facility) → convertir a bandas antes de persistir
- No devolver estadísticas de grupos < umbral mínimo
- No presentar top quartile si el subconjunto no alcanza soporte mínimo
- Fallback a grupo más amplio sin revelar el motivo exacto
- Registrar internamente toda supresión y fallback
- Agregados solo mediante jobs controlados, nunca por consultas ad hoc desde endpoints públicos
- Cada agregado registra: dimensión, cohorte, ventana, n bruto, n efectivo, método, umbral, snapshot, estado de aprobación

## Auditoría
- Auditar lecturas administrativas, exportaciones y cambios de metodología
- No registrar respuestas completas en logs
- Permitir eliminación de contacto sin destruir integridad del dataset anónimo

## Referencia completa
`docs/04_DATA_PRIVACY_AND_AGGREGATION.md` · ADR-004
