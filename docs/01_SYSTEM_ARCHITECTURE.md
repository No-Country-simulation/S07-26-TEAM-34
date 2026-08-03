# Arquitectura del sistema

## Decisión central

Construir un **modular monolith** con dos rutas separadas:

- **Ruta online:** procesa una respuesta y genera un resultado contra un snapshot publicado.
- **Ruta offline:** valida el dataset acumulado, calcula agregados, rebalancea fuentes, ejecuta backtesting y publica nuevos snapshots.

Esta separación evita que un operador reciba un resultado diferente por cambios concurrentes en el dataset y permite auditar exactamente qué referencia se utilizó.

## Flujo online

```text
Formulario
  -> API de respuestas
  -> Motor de validación
  -> Transformación de privacidad
  -> Motor de scoring
  -> Motor de grupos comparables
  -> Lectura del snapshot publicado
  -> Motor de benchmark y percentiles
  -> Motor de comparación top 25 %
  -> Motor de interpretación
  -> Resultado web + payload PDF
  -> Persistencia de resultado versionado
  -> Incorporación anónima al dataset primario pendiente
```

## Flujo offline

```text
Datos públicos versionados + respuestas primarias válidas
  -> Control de calidad y representatividad
  -> Motor de privacidad y agregación
  -> Motor de rebalanceo por dimensión y cohorte
  -> Construcción de snapshot candidato
  -> Backtesting y comparación con snapshot vigente
  -> Revisión humana
  -> Publicación de snapshot inmutable
```

## Componentes y responsabilidades

| Componente | Responsabilidad | Entrada principal | Salida principal |
|---|---|---|---|
| Motor de validación | Determinar si una respuesta puede puntuar y alimentar el dataset | Respuesta y versión del cuestionario | Estado, errores, advertencias, quality score |
| Motor de scoring | Convertir opciones en scores por pregunta y dimensión | Respuesta validada y reglas versionadas | Scores y evidencias |
| Motor de grupos comparables | Seleccionar cohorte y fallback | Atributos anonimizados/binned | Cohorte elegida, ruta de fallback, n efectivo |
| Motor benchmark | Calcular percentiles, cuartiles y confianza | Scores + snapshot | Posición relativa y estadísticas |
| Motor top quartile | Encontrar diferencias de prácticas | Respuestas/prácticas agregadas | Brechas concretas y soporte estadístico |
| Motor de rebalanceo | Combinar evidencia pública y primaria | Agregados y métricas de madurez | Pesos dinámicos y benchmark combinado |
| Motor de interpretación | Ensamblar perfil y output | Hechos estructurados | Perfil, narrativa controlada y PDF payload |
| Motor de privacidad y agregación | Pseudonimizar, suprimir y publicar agregados seguros | Respuestas y cohortes | Registros analíticos y agregados permitidos |

## Posición de los dos motores sugeridos por el equipo

La incorporación de validación y privacidad/agregación es correcta, pero no deben tratarse como módulos secundarios:

- **Validación** es la compuerta de entrada del benchmark y del dataset primario.
- **Privacidad y agregación** es la frontera que controla qué se persiste en el dominio analítico y qué puede exponerse o utilizarse para comparaciones.

## Snapshots

Un snapshot representa una versión publicada del benchmark e incluye:

- fuentes públicas incluidas;
- corte de datos primarios;
- reglas de scoring;
- definición de cohortes;
- distribuciones y cuantiles;
- prácticas del top 25 % con soporte;
- pesos de rebalanceo;
- umbrales de privacidad;
- fecha, estado y aprobación.

Los snapshots publicados son inmutables. Una corrección produce un nuevo snapshot.

## Fronteras de datos

1. **Zona de contacto opcional:** datos para entregar el PDF, separados y con retención limitada.
2. **Zona de respuestas pseudónimas:** respuestas validadas sin identidad directa.
3. **Zona analítica:** scores, bandas y atributos reducidos.
4. **Zona agregada:** métricas que superan umbrales de privacidad.
5. **Zona de publicación:** snapshots y outputs sin datos individuales.

## Patrones de resiliencia

- Idempotency key por envío.
- Resultado guardado antes de responder.
- Fallback determinista cuando el LLM no está disponible.
- Snapshot activo fijado al inicio del caso de uso.
- Jobs offline reanudables y auditables.
- Publicación atómica del snapshot.
