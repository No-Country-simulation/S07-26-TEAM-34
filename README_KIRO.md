# Paquete de arquitectura para Kiro

## Benchmark de madurez operativa para data centers

Este paquete convierte la guía inicial del proyecto en documentación ejecutable por un IDE agéntico. No contiene código de aplicación. Define el sistema que debe construirse, las decisiones que no deben improvisarse y el proceso que Kiro debe seguir para generar requisitos, diseño, tareas, implementación y pruebas.

## Decisión de enfoque

Usar un flujo **Design-First** porque el proyecto tiene restricciones metodológicas, estadísticas, de privacidad y reproducibilidad que deben fijarse antes de generar tareas.

## Cómo iniciar en Kiro

1. Copiar todo el contenido de este paquete a la raíz del repositorio.
2. Abrir Kiro en el repositorio.
3. Verificar que Kiro cargue `AGENTS.md`, `.kiro/steering/` y `.kiro/skills/`.
4. Crear una Feature Spec con flujo **Design-First / High Level Design**.
5. Usar como contexto:
   - `docs/00_PROJECT_CHARTER.md`
   - `docs/01_SYSTEM_ARCHITECTURE.md`
   - `docs/02_BENCHMARK_METHODOLOGY.md`
   - `docs/adr/`
6. Pedir a Kiro que valide y refine la spec existente en `.kiro/specs/benchmark-core/` antes de implementar.
7. Ejecutar las tareas por fases y no en una única generación masiva.

## Prompt inicial recomendado para Kiro

> Lee `AGENTS.md`, todos los archivos de `.kiro/steering/`, la skill `benchmark-engine-delivery` y los ADR vigentes. Revisa la spec `benchmark-core` con enfoque Design-First. Identifica contradicciones, dependencias y decisiones faltantes. No escribas código todavía. Primero entrega una propuesta de ajustes a `requirements.md`, `design.md` y `tasks.md`, manteniendo el núcleo determinista, la privacidad por diseño, los snapshots versionados y el rebalanceo dinámico fuera del camino transaccional.

## Estructura del paquete

- `AGENTS.md`: reglas permanentes para el agente.
- `.kiro/steering/`: contexto de producto, tecnología, estructura y gobernanza.
- `.kiro/skills/benchmark-engine-delivery/SKILL.md`: workflow reutilizable de construcción.
- `.kiro/specs/benchmark-core/`: requisitos, diseño y tareas iniciales.
- `docs/`: arquitectura detallada, metodología, datos, contratos, pruebas y roadmap.
- `docs/adr/`: decisiones arquitectónicas que Kiro no debe cambiar sin registrar una nueva decisión.

## Principio de trabajo

Los motores calculan hechos; el agente interpreta y ayuda a construir; los expertos aprueban cambios metodológicos; los snapshots publicados garantizan que un resultado pueda reproducirse después.
