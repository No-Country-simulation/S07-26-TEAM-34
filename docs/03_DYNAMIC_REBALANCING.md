# Motor de rebalanceo dinámico

## Objetivo

Iniciar con 100 % de evidencia pública y aumentar el peso de datos primarios solo cuando estos demuestren suficiente madurez. El peso no es un ratio fijo global: se calcula por dimensión, cohorte y snapshot.

## Principio

El volumen por sí solo no es suficiente. Una muestra grande pero sesgada, antigua o de baja calidad no debe desplazar una referencia pública más sólida.

## Factores de madurez primaria

Para cada dimensión y cohorte, calcular factores normalizados entre 0 y 1:

- **Suficiencia:** tamaño efectivo respecto del mínimo objetivo.
- **Calidad:** promedio ponderado de quality scores y completitud.
- **Representatividad:** cobertura de los segmentos esperados y ausencia de concentración excesiva.
- **Actualidad:** decaimiento según edad de las respuestas.
- **Estabilidad:** variación de resultados entre ventanas o bootstrap/backtests.

## Tamaño efectivo

El tamaño efectivo no es el conteo bruto. Cada respuesta aporta según su calidad, actualidad y confiabilidad. Duplicados, sospechas, baja completitud o respuestas muy antiguas reducen su contribución.

## Función de peso

La arquitectura debe usar una función saturante y monotónica:

- con cero respuestas primarias válidas, el peso primario es cero;
- al crecer la evidencia confiable, el peso aumenta gradualmente;
- una degradación de calidad o representatividad puede reducirlo;
- el peso puede diferir entre dimensiones y cohortes;
- los límites y parámetros pertenecen a una versión de rebalanceo.

Una forma recomendada es combinar los factores mediante una media geométrica o producto penalizado, evitando que un factor muy débil quede oculto por otros fuertes. El resultado se aplica como peso primario; el peso público es su complemento.

## Mezcla de distribuciones

No mezclar únicamente promedios. Para percentiles se necesita una distribución combinada o cuantiles derivados de una mezcla coherente. Las opciones aceptables deben evaluarse mediante backtesting:

1. muestra pública ponderada + muestra primaria ponderada;
2. mezcla de funciones de distribución empíricas;
3. cuantiles suavizados con prior público.

La elección definitiva se registra en un ADR metodológico.

## Publicación

El rebalanceo se ejecuta al construir un snapshot candidato. Nunca cambia un resultado ya emitido. El snapshot almacena:

- factores calculados;
- pesos por dimensión/cohorte;
- datos de entrada;
- parámetros y versión;
- métricas de estabilidad;
- motivo de aprobación o rechazo.

## Salvaguardas

- Máximo cambio permitido de peso entre snapshots, salvo aprobación especial.
- Alertas ante saltos de percentiles por segmento.
- Rechazo de publicación si se degradan privacidad o estabilidad.
- Fallback a la última versión aprobada si falla la construcción.
- Reporte de drift entre fuentes públicas y primarias.
