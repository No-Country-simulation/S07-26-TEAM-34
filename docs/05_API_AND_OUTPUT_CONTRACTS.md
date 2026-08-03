# Contratos de API y output

## Principio

La API expone casos de uso; no expone motores individuales como contratos públicos. Los motores pueden evolucionar mientras el contrato de producto se mantiene estable.

## Casos de uso

### Obtener cuestionario

Devuelve una versión publicada, dimensiones, preguntas, opciones y metadatos de presentación. No devuelve valores de scoring internos.

### Enviar respuesta

Recibe la versión, respuestas, atributos de cohorte permitidos y una clave idempotente. Devuelve un identificador pseudónimo y estado de procesamiento.

### Obtener resultado

Devuelve el output estructurado generado contra un snapshot específico.

### Generar input para PDF

Devuelve un payload estable, sin lógica estadística adicional, para que el Proyecto 5 genere el documento.

## Contenido mínimo del resultado

- identificador de resultado;
- fecha de generación;
- versión de cuestionario y metodología;
- snapshot usado;
- cohorte utilizada y nivel de especificidad;
- resultados por dimensión;
- percentil o banda percentil;
- score y referencia relevante;
- nivel de confianza;
- fricción principal;
- diferencias con el cuartil superior;
- advertencias o limitaciones;
- textos y campos preparados para PDF.

## Resultado por dimensión

Cada dimensión debe incluir:

- nombre y definición breve;
- score normalizado;
- percentil;
- banda descriptiva;
- estadística de referencia;
- confianza;
- evidencias o respuestas que explican el resultado;
- mensaje específico sin afirmaciones no soportadas.

## Payload para PDF

El endpoint de PDF no recalcula nada. Consume el resultado persistido y entrega:

- encabezado y contexto;
- resumen ejecutivo;
- cinco bloques de dimensión;
- perfil de fricción;
- comparación top 25 %;
- metodología y notas de privacidad;
- identificadores de versión y snapshot.

## Errores relevantes

- versión de cuestionario no publicada;
- respuestas incompletas o incompatibles;
- envío duplicado;
- snapshot no disponible;
- resultado suprimido por política;
- conflicto de versión;
- indisponibilidad del componente narrativo con fallback determinista.
