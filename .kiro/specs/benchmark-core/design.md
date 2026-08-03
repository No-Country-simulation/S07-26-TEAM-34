# Design — benchmark-core

## Decisión central
Modular monolith con dos rutas separadas. Referencia: ADR-001, ADR-010.

## Ruta online (transaccional)
```
POST /responses
  → ValidationEngine        # compuerta: bloquea si inválida
  → PrivacyTransform        # pseudonimización + bandas
  → ScoringEngine           # scores por dimensión desde config versionada
  → CohortEngine            # selección jerárquica + fallback
  → SnapshotReader          # fija snapshot publicado al inicio
  → BenchmarkEngine         # percentiles + confianza
  → TopQuartileEngine       # diferencias de prácticas con soporte
  → InterpretationEngine    # perfil de fricción + narrativa desde hechos
  → ResultPersistence       # guarda antes de responder
  → AnonymousDatasetQueue   # encola incorporación al dataset primario
GET /results/{id}
GET /results/{id}/pdf-payload
```

## Ruta offline (batch jobs)
```
Job: BuildSnapshotCandidate
  ← PublicDataSources (versionadas)
  ← PrimaryDataset (respuestas válidas pseudónimas)
  → QualityRepresentativenessCheck
  → PrivacyAggregationEngine   # supresión, bandas, umbrales
  → RebalancingEngine          # pesos por dimensión/cohorte
  → SnapshotCandidate          # inmutable, con todos los metadatos
  → BacktestRunner             # compara con snapshot vigente
  → HumanApprovalGate
  → PublishedSnapshot          # publicación atómica
```

## Módulos de dominio

### ValidationEngine
- Entrada: `RawResponse` + `QuestionnaireVersion`
- Salida: `ValidationResult { status, errors[], warnings[], qualityScore }`
- Reglas: completitud, consistencia, duplicados, anomalías
- Sin dependencia de DB ni LLM

### ScoringEngine
- Entrada: `ValidatedResponse` + `ScoringRules` (config versionada)
- Salida: `DimensionScores { dimension, rawScore, normalizedScore, evidence[] }[]`
- Determinista: misma entrada + mismas reglas → mismo output
- Sin dependencia de DB ni LLM

### CohortEngine
- Entrada: `AnonymizedAttributes` + `CohortDefinition` (config versionada)
- Salida: `CohortAssignment { cohortId, level, fallbackPath[], effectiveN }`
- Jerarquía: región+tipo+capacidad+workload → ... → global
- Aplica umbral de privacidad en cada nivel

### BenchmarkEngine
- Entrada: `DimensionScores` + `BenchmarkSnapshot`
- Salida: `BenchmarkResult { dimension, percentile, band, referenceStats, confidenceLevel }[]`
- Usa snapshot fijo, nunca datos vivos

### TopQuartileEngine
- Entrada: `BenchmarkSnapshot` + `CohortAssignment`
- Salida: `TopQuartileGaps { dimension, practices[], statisticalSupport }[]`
- Solo publica prácticas con muestra suficiente y diferencia material

### RebalancingEngine
- Entrada: `PrimaryDataMetrics` + `PublicDataMetrics` + `RebalancingConfig`
- Salida: `RebalancingWeights { dimension, cohort, primaryWeight, publicWeight, factors }[]`
- Solo se ejecuta en flujo offline

### InterpretationEngine
- Entrada: `BenchmarkResult[]` + `TopQuartileGaps[]` + `ValidationResult` + `InterpretationTemplates`
- Salida: `OperatorReport { frictionProfile, dimensionMessages[], executiveSummary, pdfPayload }`
- El LLM puede redactar desde hechos estructurados; fallback determinista obligatorio

### PrivacyAggregationEngine
- Entrada: `ValidatedResponses[]` + `PrivacyConfig`
- Salida: `ApprovedAggregates[]` + `AuditLog`
- Solo en flujo offline; aplica supresión, bandas y umbrales antes de exponer

## Modelo de datos (entidades core)

```
QuestionnaireVersion    id, version, publishedAt, questions[]
Question                id, dimensionId, text, options[], weight
AnswerOption            id, value, scoreValue  ← en config, no en DB pública
ResponseSession         id (aleatorio), questionnaireVersionId, idempotencyKey, receivedAt
Answer                  sessionId, questionId, optionId
ValidationResult        sessionId, status, errors[], warnings[], qualityScore
DimensionScore          sessionId, dimension, normalizedScore, evidence[], scoringVersion
CohortAssignment        sessionId, cohortId, level, fallbackPath, effectiveN, cohortVersion
BenchmarkSnapshot       id, publishedAt, status(draft|published), sources[], cutDate, ...
OperatorResult          id, sessionId, snapshotId, generatedAt, methodologyVersions, payload
AggregateMetric         id, dimension, cohort, window, nBruto, nEffective, method, snapshotId
AuditEvent              id, type, actorId, timestamp, metadata
```

## Zonas de datos (fronteras duras)
```
[Contacto opcional] ←separado→ [Respuestas pseudónimas] → [Analítica] → [Agregada] → [Publicación]
```
- El contacto nunca cruza al dominio analítico
- Los cuasi-identificadores se convierten en bandas en la zona pseudónima antes de pasar a analítica

## Contratos de API

```
GET  /questionnaires/{version}          → QuestionnaireDTO (sin scoreValues)
POST /responses                         → { responseId, status }
GET  /results/{responseId}              → OperatorResultDTO
GET  /results/{responseId}/pdf-payload  → PdfPayloadDTO (sin recalcular)
```

Errores esperados: versión no publicada, respuesta incompleta, envío duplicado, snapshot no disponible, resultado suprimido, LLM no disponible (fallback activo).

## Patrones de resiliencia
- Idempotency key en `POST /responses`
- Resultado persistido antes de devolver respuesta HTTP
- Snapshot activo fijado al inicio de cada caso de uso online
- Fallback determinista en InterpretationEngine si LLM falla
- Jobs offline reanudables con estado persistido

## Decisiones ADR vinculadas
| Decisión | ADR |
|---|---|
| Modular monolith | ADR-001 |
| Snapshots inmutables | ADR-002 |
| Validación como compuerta | ADR-003 |
| Privacidad como frontera | ADR-004 |
| Rebalanceo por dimensión/cohorte | ADR-005 |
| Cohortes jerárquicas con fallback | ADR-006 |
| Sin score compuesto en MVP | ADR-007 |
| LLM fuera del camino estadístico | ADR-008 |
| Metodología declarativa versionada | ADR-009 |
| Online/offline separados | ADR-010 |
