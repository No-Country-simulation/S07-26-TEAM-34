# Project Charter

## Nombre

Benchmark de madurez cross-layer para operadores de data centers.

## Problema

Los data centers pueden tener capacidad pagada y encendida que no produce trabajo útil porque las capas de energía, cooling y workloads se observan y coordinan de forma fragmentada. Hoy el operador carece de una referencia sectorial suficientemente específica para saber su posición relativa y qué prácticas distinguen a los operadores más maduros.

## Objetivo

Construir el motor que:

1. recibe respuestas anónimas;
2. valida su calidad;
3. calcula cinco dimensiones;
4. identifica el grupo comparable;
5. calcula percentiles y confianza;
6. caracteriza la fricción principal;
7. compara con prácticas del cuartil superior;
8. genera un output estructurado para web y PDF;
9. incorpora la respuesta al dataset primario sin exposición individual;
10. mezcla dinámicamente evidencia pública y primaria.

## Alcance del MVP

Incluye:

- cuestionario versionado;
- ocho motores de dominio;
- API y persistencia;
- snapshots de benchmark;
- output personalizado;
- payload para PDF;
- privacidad, agregación y auditoría;
- backtesting básico.

No incluye:

- ML para scoring;
- recomendaciones autónomas sin reglas;
- microservicios;
- personalización por facility identificable;
- score global único no validado;
- publicación automática de cambios metodológicos.

## Principios

- Reciprocidad: valor inmediato a cambio de datos anónimos.
- Especificidad: el resultado debe revelar una posición o brecha concreta.
- Explicabilidad: cada score y afirmación debe tener trazabilidad.
- Privacidad: ningún output agregado debe permitir inferir una respuesta individual.
- Reproducibilidad: un resultado histórico debe poder reconstruirse.
- Evolución controlada: los datos primarios ganan peso solo cuando su evidencia es suficiente.
