# Roadmap de implementación

## Fase 0 - Fundaciones

- Definir glosario y versiones metodológicas.
- Fijar preguntas, opciones, dimensiones y atributos de cohorte.
- Crear dataset público inicial con procedencia documentada.
- Aprobar umbrales de privacidad y confianza.

## Fase 1 - Núcleo determinista

- Motor de validación.
- Motor de scoring para cinco dimensiones.
- Configuración versionada.
- Pruebas unitarias, propiedades y golden cases.

**Salida:** una respuesta ficticia válida produce scores reproducibles.

## Fase 2 - Benchmark inicial

- Cohortes jerárquicas.
- Snapshot público inicial.
- Percentiles, cuartiles y confianza.
- Fallback entre cohortes.

**Salida:** un operador recibe posición por dimensión contra datos públicos.

## Fase 3 - Resultado específico

- Motor top quartile.
- Perfil de fricción.
- Motor de interpretación con plantillas deterministas.
- Contrato web y PDF.

**Salida:** resultado específico y payload estable.

## Fase 4 - Persistencia y privacidad

- Modelo de datos.
- Pseudonimización.
- Separación de contacto.
- Supresión y agregación.
- Auditoría e idempotencia.

**Salida:** respuestas incorporadas de forma segura al dataset primario.

## Fase 5 - Rebalanceo dinámico

- Calidad, representatividad, actualidad y tamaño efectivo.
- Pesos por dimensión/cohorte.
- Snapshot candidato.
- Backtesting y publicación controlada.

**Salida:** la evidencia primaria gana peso de manera documentada.

## Fase 6 - Operación y mejora continua

- Panel interno de calidad y crecimiento.
- Monitoreo de drift.
- Propuestas asistidas por LLM.
- Flujo de aprobación humana.

## Orden de trabajo en Kiro

Crear una spec por fase o por vertical de motor. Evitar una única tarea “construir todo el sistema”. Cada spec debe tener criterios de aceptación observables y dependencias explícitas.
