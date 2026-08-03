# ADR-001: Modular monolith y límites de motores

- Estado: Aceptado
- Fecha: 2026-08-03

## Contexto

El benchmark contiene múltiples cálculos relacionados, pero el volumen inicial y el tamaño del equipo no justifican microservicios. La separación lógica sigue siendo necesaria para probar y versionar cada responsabilidad.

## Decisión

Construir un modular monolith. Cada motor será un módulo de dominio con contratos explícitos y sin dependencia de API, ORM o LLM. La capa de aplicación orquestará motores y persistencia.

## Consecuencias

- Menor complejidad operativa.
- Pruebas aisladas y refactor futuro posible.
- Requiere disciplina para evitar dependencias cruzadas.
- Una separación en servicios solo se evaluará por límites de escalado, ownership o seguridad demostrados.
