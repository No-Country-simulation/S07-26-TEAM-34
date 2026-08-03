# Tasks — benchmark-core

## Estado de fases

### FASE 0 — Fundaciones metodológicas
> Precondición: el equipo cierra preguntas, pesos, fuentes públicas y umbrales de privacidad.

- [x] **T-00-1** Definir glosario y versiones metodológicas iniciales
- [x] **T-00-2** Fijar estructura de config versionada (preguntas, opciones, pesos, cohortes)
  - `config/methodology/1.0.0/questionnaire.yaml` — 20 preguntas ficticias, 5 dimensiones
  - `config/methodology/1.0.0/cohorts.yaml` — jerarquía de 5 niveles
  - `config/methodology/1.0.0/privacy.yaml` — umbrales de privacidad
- [ ] **T-00-3** Documentar dataset público inicial con procedencia y licencia ← pendiente equipo
- [ ] **T-00-4** Aprobar umbrales de privacidad definitivos ← pendiente equipo

---

### FASE 1 — Núcleo determinista ✅
> Completa.

- [x] **T-01-1** `ValidationEngine` — compuerta de entrada con quality score
- [x] **T-01-2** `ScoringEngine` — determinista, monotonicidad verificada, evidencia por pregunta
- [x] **T-01-3** Loader de config metodológica con `lru_cache` y resolución de ruta flexible
- [x] **T-01-4** Tests unitarios + propiedades (Hypothesis) + integración → **32/32 pasando**

---

### FASE 2 — Benchmark inicial ✅
> Completa.

- [x] **T-02-1** `CohortEngine` — jerarquía con fallback, supresión por privacidad
- [x] **T-02-2** `SnapshotBuilder` — construye distribuciones y prácticas top quartile (flujo offline)
- [x] **T-02-3** `BenchmarkEngine` — percentiles interpolados, confianza por n_effective
- [x] **T-02-4** Tests de integración flujo completo con snapshot de prueba

---

### FASE 3 — Resultado específico ✅
> Completa.

- [x] **T-03-1** `TopQuartileEngine` — gaps con soporte estadístico, sin causalidad implícita
- [x] **T-03-2** `InterpretationEngine` — perfil de fricción, mensajes específicos, fallback determinista
- [x] **T-03-3** Contratos `OperatorResultOut` y `PdfPayloadOut` en `api/schemas.py`
- [x] **T-03-4** Endpoints `GET /results` y `GET /results/{id}/pdf-payload` (pdf no recalcula)

---

### FASE 4 — Persistencia y privacidad ✅
> Completa.

- [x] **T-04-1** Modelo de datos con 5 zonas separadas (`db/models.py`)
  - ContactStore sin FK hacia analítica; bandas en lugar de valores exactos
- [x] **T-04-2** Pseudonimización: ID aleatorio, bandas de cohorte, hash de contacto
- [x] **T-04-3** `PrivacyAggregationEngine` básico integrado en `SnapshotBuilder`
- [x] **T-04-4** Idempotencia persistida en DB por `idempotency_key`
- [x] **T-04-5** Tests de privacidad: grupos separados, sin PII en analítica, purga de contacto
- [x] Alembic configurado: `alembic upgrade head` crea el esquema completo
- [x] `db/seed.py` genera snapshot inicial sintético para desarrollo

---

### FASE 5 — Rebalanceo dinámico y job offline ✅
> Completa.

- [x] **T-05-1** 5 factores de madurez primaria (suficiencia, calidad, representatividad, actualidad, estabilidad)
- [x] **T-05-2** `RebalancingEngine` con media geométrica, invariante peso suma 1.0
- [x] **T-05-3** `jobs/build_snapshot.py` — job reanudable con CLI
  - Carga pendientes → analítica → rebalanceo → snapshot candidato → backtest → DRAFT
  - `--force-publish --approved-by "nombre"` publica si pasa backtest
- [x] **T-05-4** Backtest básico: drift p50 > 0.20 rechaza el snapshot automáticamente
- [x] **T-05-5** 8 tests del job offline incluyendo detección de drift alto

---

### FASE 6 — Operación y mejora continua ✅
> Completa.

- [x] **T-06-1** Panel interno (`monitoring/dashboard.py` + `GET /admin/v1/dashboard`)
  - Métricas de crecimiento, acceptance rate, calidad por dimensión, drift entre snapshots, auditoría 24h
- [x] **T-06-2** Monitor de drift (`monitoring/drift_monitor.py` + `GET /admin/v1/drift-alerts`)
  - Alertas warning (Δp50 ≥ 0.10) y critical (Δp50 ≥ 0.20), detección de caída de n_effective
- [x] **T-06-3** Flujo LLM con aprobación humana (`engines/llm_interpretation.py`)
  - Propuestas PENDING → aprobación/rechazo explícito con nombre de revisor
  - Fallback determinista cuando no hay cliente LLM (ADR-008)
  - Endpoints: `POST /admin/v1/proposals/{narrative|methodology}`, approve, reject
- [x] **T-06-4** Validación metodológica (`jobs/methodology_update.py`)
  - Checklist de 9 puntos antes de publicar una nueva versión
  - CLI: `python -m benchmark.jobs.methodology_update --version X.Y.Z --check`
  - Endpoint: `POST /admin/v1/methodology/validate/{version}`
- [x] Panel admin completo en `api/admin_routes.py` con publicación de snapshots supervisada

---

## Definición de terminado (global)
Una tarea está terminada cuando:
- cumple sus criterios de aceptación
- mantiene contratos existentes o documenta su cambio
- incluye pruebas con datos no sensibles
- registra versión, trazabilidad y errores relevantes
- no debilita umbrales de privacidad
- conserva reproducibilidad respecto del snapshot y metodología
- deja actualizados spec, documentación y ADR afectados
