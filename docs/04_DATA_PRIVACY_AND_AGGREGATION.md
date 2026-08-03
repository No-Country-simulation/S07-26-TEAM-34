# Datos, privacidad y agregación

## Objetivo

Almacenar suficiente información para construir el benchmark sin conservar o exponer elementos que permitan identificar a un operador o facility.

## Entidades conceptuales

- `QuestionnaireVersion`: definición publicada del diagnóstico.
- `Question` y `AnswerOption`: contenido y reglas versionadas.
- `ResponseSession`: envío pseudónimo e idempotente.
- `Answer`: respuesta por pregunta.
- `ValidationResult`: errores, advertencias y quality score.
- `DimensionScore`: score y evidencia por dimensión.
- `CohortAssignment`: cohorte, fallback y tamaño efectivo.
- `BenchmarkSnapshot`: referencia publicada e inmutable.
- `OperatorResult`: output generado y versiones utilizadas.
- `AggregateMetric`: estadística aprobada para uso analítico.
- `MethodologyVersion`: conjunto de versiones relacionadas.
- `AuditEvent`: acceso o cambio relevante.

## Identidad y pseudonimización

- El identificador de respuesta debe ser aleatorio y no derivado de datos del operador.
- Si se solicita email para entregar resultados, guardarlo en un almacén separado y no utilizarlo para scoring o cohortes.
- La relación entre contacto y respuesta debe tener acceso restringido, retención limitada y propósito explícito.

## Cuasi-identificadores

Variables como capacidad exacta, localización precisa, edad del facility o combinaciones poco frecuentes pueden reidentificar. Deben:

- convertirse en bandas;
- generalizarse cuando la cohorte sea pequeña;
- excluirse de outputs públicos;
- someterse a revisión de unicidad.

## Estados de una respuesta

1. Recibida.
2. Validada o rechazada.
3. Pseudonimizada.
4. Puntuada.
5. Incorporada al dataset primario pendiente.
6. Incluida en un snapshot publicado, si corresponde.

Una respuesta rechazada puede conservar métricas operativas mínimas, pero no debe alimentar el benchmark.

## Supresión

- No devolver estadísticas de grupos por debajo del mínimo configurado.
- No presentar top quartile si el subconjunto superior no alcanza el soporte mínimo.
- Usar fallback a un grupo más amplio sin revelar el motivo exacto cuando hacerlo facilite inferencia.
- Registrar internamente la supresión y el fallback.

## Agregación

Los agregados deben construirse en jobs controlados y no mediante consultas ad hoc desde endpoints públicos. Cada agregado registra:

- dimensión y cohorte;
- ventana temporal;
- tamaño bruto y efectivo;
- método de cálculo;
- umbral de privacidad;
- snapshot de destino;
- estado de aprobación.

## Auditoría y retención

- Auditar lecturas administrativas, exportaciones y cambios de metodología.
- No registrar respuestas completas en logs.
- Definir retención distinta para contacto, respuestas, resultados y auditoría.
- Permitir eliminación del contacto sin destruir la integridad del dataset anónimo cuando sea legal y metodológicamente válido.
