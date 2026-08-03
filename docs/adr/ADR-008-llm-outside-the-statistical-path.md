# ADR-008: LLM fuera del camino estadístico

- Estado: Aceptado
- Fecha: 2026-08-03

## Contexto

Un LLM puede mejorar redacción, pero no garantiza resultados deterministas ni reproducibles.

## Decisión

El LLM solo puede interpretar hechos estructurados y redactar. No calcula scores, percentiles, cohortes, pesos, cuartiles o agregados. Debe existir un fallback determinista.

## Consecuencias

- Resultados válidos aun sin proveedor LLM.
- Menor riesgo de alucinación metodológica.
- Las plantillas y prompts también deben versionarse.
