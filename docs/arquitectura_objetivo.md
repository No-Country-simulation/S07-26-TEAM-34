# Arquitectura Objetivo del Proyecto

## Resumen

Este documento define la arquitectura objetivo del proyecto y aclifica la inconsistencia entre las dos implementaciones existentes en el repositorio.

## Arquitectura Objetivo: Versión Simple (app/)

**Esta es la arquitectura definitiva para el proyecto**, basada en `Guia_PRs_Migracion.md`.

### Estructura de Directorios

```
.
├── app/                          # Implementación principal
│   ├── api/                      # Routers FastAPI
│   │   └── routers.py
│   ├── config/                   # Configuración
│   │   ├── dimensiones.yaml     # Fuente única de preguntas/opciones/scores
│   │   ├── loader.py            # Loader del YAML
│   │   ├── seed_public_dataset.py # Script de seed (PR 1)
│   │   └── dataset_publico_sintetico.csv # Dataset sintético
│   ├── engines/                  # Motores de cálculo (determinísticos)
│   │   ├── scoring_engine.py    # Motor de scoring (PR 6)
│   │   ├── rebalance_engine.py  # Motor de rebalanceo (PR 10)
│   │   ├── benchmark_engine.py  # Motor de percentiles
│   │   ├── top_quartile_engine.py # Comparación top 25%
│   │   ├── interpretation_engine.py # Interpretación + LLM
│   │   └── privacy_engine.py    # Generación de UUIDs
│   ├── models/                   # Modelos SQLAlchemy
│   │   ├── database.py          # Conexión a BD
│   │   └── tables.py            # 3 tablas: operators, dimension_scores, results
│   ├── repositories/            # Acceso a datos
│   │   └── benchmark_repository.py
│   ├── schemas/                  # Schemas Pydantic
│   │   ├── request.py           # Request schemas
│   │   └── response.py          # Response schemas
│   ├── services/                 # Orquestador
│   │   └── benchmark_service.py
│   └── prompts/                  # Plantillas LLM
│       └── diagnostico.txt
├── tests/                        # Tests (misma estructura que app/)
│   ├── api/
│   ├── config/
│   ├── engines/
│   ├── models/
│   ├── schemas/
│   └── services/
├── config/                       # Configuración global
│   └── dimensiones.yaml         # Archivo maestro
├── main.py                       # Entry point FastAPI
└── requirements.txt              # Dependencias
```

### Base de Datos

**3 tablas exactamente** (según backlog sección 11):

1. **operators** - Una fila por cuestionario completado
2. **dimension_scores** - Una fila por operador y dimensión (5 filas por operador)
3. **results** - Una fila por operador con resultado calculado

**Sin tablas adicionales** de auditoría, snapshots, contactos, etc.

### Dataset Público Sintético

- **Archivo**: `config/dataset_publico_sintetico.csv`
- **Script de carga**: `config/seed_public_dataset.py`
- **Generación**: Usando faker para datos realistas
- **Carga**: 1,000 registros iniciales con `source="public_synthetic"`
- **Actualización**: En runtime desde `dimension_scores` filtrando por `source`

## Inconsistencia Arquitectónica

### Problema Identificado

El repositorio contiene **dos implementaciones diferentes**:

1. **app/** - Versión simple (arquitectura objetivo)
2. **src/benchmark/** - Versión compleja con snapshots

### Diferencias Clave

| Aspecto | app/ (Objetivo) | src/benchmark/ (Diferente) |
|---------|-----------------|----------------------------|
| Complejidad | Simple, directo | Complejo con snapshots |
| Tablas BD | 3 tablas básicas | 5+ tablas con snapshots |
| Dataset | CSV + seed simple | Sistema de snapshots complejo |
| Arquitectura | Monolítica simple | Modular compleja |
| Especificación | Guia_PRs_Migracion.md | .kiro/specs/benchmark-core/ |
| Estado | ✅ Implementada | ❌ Implementación parcial |

### Origen de la Inconsistencia

1. **Specs divergentes**: `Guia_PRs_Migracion.md` define la versión simple, mientras `.kiro/specs/` define una versión más compleja
2. **Implementación mixta**: El código actual implementa la versión simple pero mantiene artefactos de la versión compleja
3. **Documentación desactualizada**: El `Backlog_Definitivo_v3.md` menciona el CSV como "ya generado" pero no existía

### Resolución

**Decisión tomada**: Usar la arquitectura simple de `app/` como objetivo definitivo.

**Acciones realizadas**:
1. ✅ Crear `config/seed_public_dataset.py` para generar el dataset sintético
2. ✅ Generar `config/dataset_publico_sintetico.csv` con 1,000 registros usando faker
3. ✅ Actualizar `benchmark_service.py` para cargar dataset desde BD en lugar de memoria
4. ✅ Documentar esta inconsistencia en `docs/arquitectura_objetivo.md`

**Acciones pendientes**:
- [ ] Decidir qué hacer con `src/benchmark/` (archivar, eliminar, o mantener como referencia)
- [ ] Actualizar `.kiro/specs/` para alinear con la arquitectura simple
- [ ] Actualizar `Backlog_Definitivo_v3.md` para reflejar la arquitectura objetivo

## Motivación de la Arquitectura Simple

**Razones para elegir la versión simple**:

1. **MVP más rápido**: Menos complejidad = más rápido de implementar y mantener
2. **Suficiente para el requerimiento**: El brief no requiere snapshots complejos
3. **Más mantenible**: Menos piezas móviles = menos puntos de falla
4. **Claridad arquitectónica**: Estructura más fácil de entender para nuevos desarrolladores
5. **Alineación con Guia_PRs_Migracion.md**: Este documento es la guía de implementación actual

## Próximos Pasos

1. **Validar que el seed funciona correctamente** con tests según PR 1
2. **Eliminar o archivar** `src/benchmark/` para evitar confusión
3. **Actualizar documentación** para reflejar que la arquitectura simple es la definitiva
4. **Comunicar al equipo** la decisión arquitectónica

## Conclusión

La arquitectura objetivo es la **versión simple definida en `app/`** según `Guia_PRs_Migracion.md`. La implementación en `src/benchmark/` representa una versión más compleja que fue considerada pero finalmente no elegida como arquitectura definitiva.
