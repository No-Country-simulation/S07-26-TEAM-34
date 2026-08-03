# Metodología del benchmark

## Unidad de análisis

Una respuesta válida de un operador para una versión específica del cuestionario. El sistema no debe asumir que múltiples respuestas pseudónimas pertenecen al mismo facility salvo que exista un mecanismo de control compatible con la privacidad.

## Las cinco dimensiones

### 1. Visibilidad cross-layer

Evalúa si energía, cooling y workloads se observan de manera conjunta, con qué frecuencia y con qué capacidad de diagnóstico.

### 2. Atribución de fricción

Evalúa si el operador puede localizar la pérdida de capacidad en una interfaz concreta entre capas y respaldarla con evidencia.

### 3. Latencia de coordinación

Evalúa el tiempo transcurrido entre un cambio de workload y el ajuste correspondiente de cooling y energía.

### 4. Auto-cuantificación

Evalúa si el operador estima stranded capacity, la frecuencia de cálculo, cobertura y nivel de confianza.

### 5. Bloqueantes

Clasifica los obstáculos que impiden actuar: visibilidad, integración, ownership, procesos, presupuesto, riesgo operativo, vendor lock-in u otros definidos por metodología.

## Scoring

- Cada pregunta se asigna a una dimensión.
- Cada opción tiene un valor explícito y versionado.
- Las preguntas pueden tener pesos diferentes.
- Los scores se normalizan en una escala común por dimensión.
- Las respuestas abiertas no alteran directamente el score salvo reglas humanas previamente aprobadas.
- El resultado debe conservar evidencia de qué respuestas contribuyeron a cada dimensión.

## Score general

No se recomienda publicar un único score general en el MVP. Las cinco dimensiones representan mecanismos distintos y un promedio puede ocultar una fricción crítica. Un score general solo debe introducirse después de validar su interpretación, estabilidad y utilidad.

## Grupos comparables

La comparación se resuelve de forma jerárquica. Ejemplo de orden:

1. región + tipo de data center + banda de capacidad + workload;
2. región + tipo + banda de capacidad;
3. tipo + banda de capacidad;
4. tipo;
5. benchmark global.

El motor selecciona el grupo más específico que cumpla tamaño efectivo y privacidad. El output debe mostrar qué grupo se utilizó y si hubo fallback.

## Percentiles

- Calcular por dimensión, no sobre respuestas crudas.
- Definir de manera explícita el tratamiento de empates.
- Utilizar el snapshot publicado.
- Mostrar nivel de confianza o calidad de referencia.
- Evitar precisión falsa: la UI puede presentar bandas o percentiles redondeados cuando la muestra sea limitada.

## Cuartil superior

El top 25 % se calcula por dimensión o perfil relevante, no necesariamente por un score general. Para afirmar que una práctica distingue al cuartil superior debe existir:

- suficiente muestra;
- diferencia material frente al resto;
- soporte mínimo de frecuencia;
- cumplimiento de umbrales de privacidad;
- redacción que no implique causalidad no demostrada.

## Perfil de fricción principal

Se determina mediante reglas versionadas que combinan:

- dimensión con peor posición relativa;
- severidad absoluta del score;
- consistencia entre preguntas;
- patrón de interfaces o bloqueantes;
- confianza del benchmark usado.

El perfil debe ser específico, por ejemplo: “baja latencia de observación pero coordinación manual entre workload y cooling”, en lugar de “necesita mejorar eficiencia”.

## Confianza

La confianza debe considerar como mínimo:

- tamaño efectivo de muestra;
- calidad de respuestas;
- representatividad del segmento;
- actualidad de datos;
- dependencia de fallback global.

La confianza no debe confundirse con probabilidad de que el operador sea “bueno” o “malo”. Describe la solidez de la comparación.
