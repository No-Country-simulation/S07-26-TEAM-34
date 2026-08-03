# Riesgos y decisiones abiertas

## Riesgos principales

### Dataset público insuficiente o no comparable

Mitigación: registrar procedencia, alcance, fecha y mapeo; expresar confianza; no presentar precisión inexistente.

### Sesgo de autoselección

Los operadores que responden pueden no representar la industria. Mitigación: medir cobertura, ponderar representatividad y no aumentar peso primario solo por volumen.

### Reidentificación

Cohortes muy específicas pueden revelar a un facility. Mitigación: bandas, supresión, fallback y separación de contacto.

### Percentiles inestables

Muestras pequeñas generan posiciones volátiles. Mitigación: snapshots, tamaño efectivo, bandas, confianza y backtesting.

### Narrativa genérica o exagerada

Mitigación: el texto se genera desde hechos estructurados; plantillas de fallback; validación de soporte.

### Cambio metodológico opaco

Mitigación: ADR, versionado, backtesting y snapshots inmutables.

## Decisiones que el equipo debe cerrar

1. Preguntas exactas y escala de respuestas.
2. Pesos por dimensión.
3. Fuentes públicas y licencias.
4. Definición de población objetivo para representatividad.
5. Umbrales de tamaño efectivo y privacidad.
6. Método de percentil y empates.
7. Función exacta de rebalanceo.
8. Definición estadística de “práctica distintiva” del top 25 %.
9. Política de retención y entrega de PDF.
10. Necesidad futura de un score general.
