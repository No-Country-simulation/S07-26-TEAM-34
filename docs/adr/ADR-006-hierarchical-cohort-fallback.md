# ADR-006: Cohortes jerárquicas con fallback

- Estado: Aceptado
- Fecha: 2026-08-03

## Contexto

La comparación más específica puede no tener muestra suficiente o puede vulnerar privacidad.

## Decisión

Definir una jerarquía versionada de cohortes. Seleccionar la más específica que cumpla tamaño efectivo y privacidad. Registrar el camino de fallback y reducir confianza cuando corresponda.

## Consecuencias

- Siempre existe una referencia utilizable.
- Algunas comparaciones serán menos específicas.
- La UI debe comunicar el nivel de comparación.
