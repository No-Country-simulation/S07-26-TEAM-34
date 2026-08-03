# Estrategia de pruebas y backtesting

## Objetivos

- demostrar corrección de reglas;
- proteger invariantes estadísticas;
- impedir regresiones metodológicas;
- verificar privacidad;
- garantizar reproducibilidad.

## Capas de prueba

### Unitarias

Por motor, sin base de datos ni API:

- mapeos de scoring;
- normalización y límites;
- contradicciones de validación;
- selección de cohortes;
- tratamiento de empates;
- cálculo de confianza;
- factores de rebalanceo;
- reglas de supresión.

### Basadas en propiedades

Invariantes recomendados:

- scores siempre dentro del rango;
- mejorar una respuesta monotónica no reduce su score;
- percentiles dentro de 0 a 100;
- peso público + primario = 1;
- sin datos primarios, peso primario = 0;
- un agregado suprimido nunca aparece en output;
- el mismo input, versiones y snapshot producen el mismo resultado.

### Integración

- envío completo desde API a persistencia;
- idempotencia;
- transacciones y fallos parciales;
- lectura de snapshot activo;
- generación del payload PDF;
- separación entre contacto y respuesta.

### Golden tests

Mantener casos representativos con resultados esperados por versión metodológica. Un cambio de golden output requiere explicación y aprobación.

### Privacidad

- grupos pequeños;
- combinaciones únicas;
- logs;
- exports;
- permisos administrativos;
- eliminación de contacto;
- ausencia de identificadores directos en dataset analítico.

## Backtesting metodológico

Para cada snapshot candidato comparar con el vigente:

- distribución de scores y percentiles;
- cambios por dimensión y cohorte;
- estabilidad de perfiles de fricción;
- prácticas top quartile agregadas o eliminadas;
- variación de pesos público/primario;
- porcentaje de operadores que cambia de cuartil;
- sensibilidad a outliers y respuestas de baja calidad;
- privacidad y tamaños efectivos.

## Criterios de rechazo

Rechazar o revisar un snapshot cuando:

- produce saltos no explicados;
- reduce la muestra efectiva por debajo de umbrales;
- aumenta afirmaciones genéricas;
- debilita supresión o anonimato;
- cambia resultados sin trazabilidad;
- presenta drift no analizado entre fuentes.
