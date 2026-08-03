# Requirements — benchmark-core

## Contexto
Motor de benchmark de madurez operativa para data centers. Recibe respuestas anónimas de operadores, calcula posición relativa en cinco dimensiones y genera un output explicable para web y PDF.

## Requisitos funcionales

### RF-01 Cuestionario versionado
- El sistema expone una versión publicada del cuestionario con preguntas, opciones y metadatos
- No expone valores de scoring internos al cliente
- Una versión publicada es inmutable

### RF-02 Validación como compuerta
- Toda respuesta pasa por validación antes de scoring y antes de incorporarse al dataset
- La salida incluye: estado (válida/rechazada), errores bloqueantes, advertencias y quality score
- Una respuesta rechazada no alimenta scores publicados ni el dataset primario

### RF-03 Scoring por dimensión
- Cinco dimensiones: visibilidad cross-layer, atribución de fricción, latencia de coordinación, auto-cuantificación, bloqueantes
- Cada opción tiene un valor explícito y versionado en config declarativa
- Los scores se normalizan en escala común por dimensión
- El resultado conserva evidencia de qué respuestas contribuyeron a cada dimensión
- No existe score general en el MVP

### RF-04 Grupos comparables con fallback jerárquico
- Jerarquía: región+tipo+capacidad+workload → región+tipo+capacidad → tipo+capacidad → tipo → global
- Se selecciona el grupo más específico que cumpla tamaño efectivo y umbral de privacidad
- El output registra qué nivel de cohorte se usó y si hubo fallback

### RF-05 Percentiles y confianza
- Calculados por dimensión sobre el snapshot publicado, no sobre datos vivos
- Tratamiento de empates explícito y versionado
- Confianza considera: tamaño efectivo, calidad de respuestas, representatividad, actualidad, dependencia de fallback
- La UI puede mostrar bandas cuando la muestra es limitada

### RF-06 Comparación con top 25%
- Top quartile calculado por dimensión, no por score general
- Una práctica solo se publica como distintiva si tiene: muestra suficiente, diferencia material, soporte de frecuencia, cumplimiento de privacidad
- La redacción no implica causalidad no demostrada

### RF-07 Perfil de fricción principal
- Determinado por reglas versionadas: peor posición relativa, severidad absoluta, consistencia entre preguntas, patrón de bloqueantes, confianza del benchmark
- El perfil debe ser específico (ej: "baja latencia de observación pero coordinación manual"), no genérico

### RF-08 Output web y payload PDF
- Resultado web: identificador, fecha, versiones, snapshot, cohorte, scores por dimensión, percentiles, confianza, fricción, comparación top 25%, advertencias
- Payload PDF: endpoint separado que consume el resultado persistido, no recalcula nada
- Cada dimensión incluye: score normalizado, percentil, banda descriptiva, estadística de referencia, confianza, evidencias, mensaje específico

### RF-09 Privacidad y pseudonimización
- ID de respuesta aleatorio, no derivado de datos del operador
- Email (si se solicita) en almacén separado, sin acceso desde scoring o cohortes
- Cuasi-identificadores convertidos a bandas antes de persistir
- No exponer grupos < umbral mínimo configurado

### RF-10 Incorporación al dataset primario
- La respuesta válida se incorpora de forma anónima al dataset primario pendiente
- La incorporación efectiva al benchmark ocurre en el siguiente snapshot offline
- Idempotencia garantizada por clave de envío

### RF-11 Snapshots inmutables
- Todo resultado se calcula contra un snapshot publicado y fijado al inicio del caso de uso
- Un snapshot incluye: fuentes, corte de datos, reglas de scoring, cohortes, distribuciones, prácticas top 25%, pesos de rebalanceo, umbrales, fecha, aprobación
- Una corrección produce un nuevo snapshot, no modifica el anterior

### RF-12 Rebalanceo dinámico (offline)
- Peso primario calculado por dimensión y cohorte usando 5 factores: suficiencia, calidad, representatividad, actualidad, estabilidad
- El rebalanceo se ejecuta al construir snapshots candidatos, nunca durante solicitudes online
- El snapshot almacena todos los factores, pesos y parámetros usados

## Requisitos no funcionales

### RNF-01 Determinismo
- El mismo input + misma versión de metodología + mismo snapshot → siempre el mismo resultado

### RNF-02 Trazabilidad
- Cada resultado registra: versión de cuestionario, versión de scoring, versión de cohortes, snapshot usado, cohorte aplicada, fallbacks ejecutados

### RNF-03 Resiliencia
- Fallback determinista cuando el LLM no está disponible
- Snapshot activo fijado al inicio del caso de uso
- Jobs offline reanudables y auditables
- Resultado guardado antes de responder al cliente

### RNF-04 Privacidad por diseño
- Privacidad y agregación son frontera de persistencia, no filtro posterior
- Los agregados se construyen en jobs controlados, nunca por consultas ad hoc

### RNF-05 Auditabilidad
- Cambios de metodología, lecturas administrativas y exportaciones se auditan
- Las versiones metodológicas se almacenan en config versionada, no en código

## Criterios de aceptación globales
- Una respuesta ficticia válida produce scores reproducibles en cualquier entorno
- Un operador recibe posición por dimensión contra un snapshot publicado
- El sistema rechaza una respuesta inválida antes de que toque el scoring
- El resultado puede reconstruirse dado el input original, la versión de metodología y el snapshot
- No se expone ningún dato individual en outputs públicos
