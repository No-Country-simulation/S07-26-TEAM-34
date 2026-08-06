# Documento Metodológico — Benchmark de Madurez en Data Centers

> **Benchmark de madurez · Data centers**
>
> Documento vivo: se va completando dimensión por dimensión a medida que se van cerrando. Sirve como marco de referencia técnico para el equipo y como respaldo metodológico ante cualquier auditoría del enfoque.

## 0. Qué mide este benchmark

Este benchmark mide la **madurez de coordinación cross-layer** de un data center: la capacidad organizacional para observar, localizar, reaccionar ante, cuantificar y remover las fricciones que existen entre energía, cooling y workload.

Mide **capacidad organizacional, no desempeño verificado**: no audita si las prácticas declaradas efectivamente se ejecutan, sino si la organización tiene, según su propio reporte, la capacidad de observarlas y actuar sobre ellas.

Las cinco dimensiones no son una lista arbitraria: describen una secuencia lógica de cómo una organización enfrenta un problema de coordinación:

```text
Visibilidad          → ¿puede verlo?
      ↓
Atribución           → ¿puede localizarlo?
      ↓
Latencia             → ¿puede reaccionar a tiempo?
      ↓
Auto-cuantificación  → ¿puede medirlo objetivamente?
      ↓
Bloqueantes          → ¿puede remover lo que le impide resolverlo?
```

Esta hipótesis de fondo —**mayor coordinación → menor stranded capacity**— no está probada con evidencia directa en este documento. Es la premisa de negocio del proyecto, no un hallazgo estadístico propio. Se declara así de manera explícita para no disfrazarla de evidencia.

## 1. Las cinco dimensiones del benchmark

| # | Dimensión | Qué mide (resumen) |
|---:|---|---|
| 1 | **Visibilidad cross-layer** | Si el operador tiene una vista unificada de energía, cooling y workload, o si cada capa se gestiona de forma aislada. Cerrada; ver sección 4. |
| 2 | **Atribución de fricción** | En qué interfaz entre capas —energía-cooling, cooling-workload o workload-energía— percibe el operador que se pierde más capacidad. Cerrada; ver sección 5. |
| 3 | **Latencia de coordinación** | Qué tan rápido se ajustan cooling y energía cuando cambia el workload y cuánto de ese ajuste depende de intervención humana. Cerrada; ver sección 3. |
| 4 | **Auto-cuantificación** | Si el operador sabe, en números concretos, cuánta capacidad tiene varada, o no tiene forma de medirlo. Cerrada; ver sección 6. |
| 5 | **Bloqueantes** | Qué le impediría al operador resolver el problema si supiera exactamente dónde está: presupuesto, política interna, herramientas o autoridad. Cerrada; ver sección 7. |

## 2. Marco metodológico general

Estas son las reglas de diseño que aplican a todas las dimensiones, no solo a la primera. Están acá para no tener que redecidirlas cada vez y para que cualquiera que se sume al equipo entienda el criterio sin tener que preguntarlo.

### 2.1. No existe un estándar de mercado para esto

No hay una tabla oficial de la industria que diga cómo puntuar estas respuestas. Este benchmark es, según el propio proyecto, el primero en medir estas dimensiones.

Toda escala de puntuación que se define acá es una decisión de diseño del equipo, documentada explícitamente como tal, no un dato externo verificado.

### 2.2. Normalización antes de combinar —evitar mezclar escalas—

Cada pregunta puede tener una naturaleza estadística distinta:

- variable numérica de razón, por ejemplo minutos;
- variable categórica ordinal, por ejemplo «automatizado/manual»;
- variable binaria;
- otras formas de captura.

Nunca se combinan valores crudos de distinta naturaleza directamente. Cada pregunta se normaliza primero a una escala común de **0 a 100** mediante su propia función de conversión, y recién los valores ya normalizados se combinan entre sí.

Esto sigue la lógica estándar de construcción de índices compuestos; véase *OECD Handbook on Constructing Composite Indicators*.

### 2.3. Escala lineal como punto de partida, no como verdad definitiva

Salvo que haya una razón concreta para lo contrario, la conversión de una respuesta ordinal a score usa una escala lineal equiespaciada:

| Cantidad de niveles | Escala |
|---:|---|
| 5 | 100 - 75 - 50 - 25 - 0 |
| 4 | 100 - 67 - 33 - 0 |
| 3 | 100 - 50 - 0 |

Se elige lineal por ausencia de datos o de un panel de expertos que permita calibrar pesos con mayor rigor estadístico —ver 2.4—. No es la opción «más precisa»; es la opción que menos supuestos no justificados introduce mientras no hay evidencia para hacer algo mejor.

> **Corrección de auditoría:** varias tablas del documento habían quedado con pasos desiguales —por ejemplo, 100-60-30-0— por error de tipeo, no por una decisión metodológica. Se corrigieron para respetar esta regla.

### 2.4. Camino a mayor rigor estadístico —fase futura, no MVP—

Existen métodos más rigurosos para calibrar estos pesos con evidencia real:

- **Item Response Theory —IRT—:** calibra los pesos a partir de patrones de respuesta de una muestra real amplia. Requiere volumen de datos primarios que el proyecto no tiene al arrancar.
- **AHP —Analytic Hierarchy Process—:** pondera por juicio experto mediante comparaciones estructuradas de a pares. Requiere un panel de expertos del rubro.

Ninguno de los dos es aplicable en el MVP por falta de insumos —datos o expertos—. Se documenta como mejora futura, ligada a la pieza de backtesting/recalibración que quedó fuera del scope inicial del proyecto, pero que es el mecanismo natural para revisar esto cuando haya suficiente dataset primario.

### 2.5. Se conserva siempre el valor crudo

Además del score normalizado de 0 a 100, se almacena el valor original de la respuesta —el número exacto de minutos, la categoría elegida, etc.—.

Esto permite recalcular o recalibrar en el futuro sin haber perdido información en el camino.

### 2.6. Preguntas diagnósticas —nominales— vs. preguntas de madurez —ordinales—

No todas las preguntas de una dimensión alimentan el índice numérico.

En dimensiones donde la respuesta principal identifica una categoría sin orden de mejor/peor —por ejemplo, «¿en qué interfaz perdés más capacidad?» o «¿qué te bloquea?»—, esa pregunta es **nominal**: se guarda tal cual y se usa directamente como insumo del motor de interpretación —3.7— para el texto cualitativo, pero no entra en el promedio del score.

El score de esas dimensiones se construye únicamente con las preguntas que sí son ordinales —por ejemplo, «¿qué tan basada en datos está esa percepción?» o «¿qué tan severo es ese bloqueante?»—, que miden madurez/severidad y sí tienen una dirección de mejor a peor.

### 2.7. Calibración del dataset público inicial —simulado—

El dataset público inicial contra el que se comparan las primeras respuestas es **sintético**, no un dataset real de encuestas de estas dimensiones —no existe tal cosa—.

Las 1.000 filas que lo componen representan simulaciones calibradas, no 1.000 operadores reales. Es una distinción importante: no hay «mil data centers» detrás de ese número; hay mil combinaciones de respuestas generadas siguiendo una distribución que el equipo definió.

Se calibra de forma aproximada usando reportes públicos reales de la industria como referencia de rango, no como fuente exacta:

- **Uptime Institute — Global Data Center Survey 2025/2026:** PUE promedio 1.54, estancado durante seis años; 45 % de incidentes graves por causas de energía.
- **EkkoSense / Sunbird DCIM:** reportes de stranded capacity; 20-40 % de capacidad de energía desperdiciada por ineficiencias de coordinación.

Esta calibración es un supuesto de diseño y debe quedar documentada como tal en cualquier output que se muestre al usuario final. Nunca debe presentarse como si fuera un dataset real de la industria.

---

## 3. Latencia de coordinación

**Qué mide:** qué tan rápido se ajustan cooling y energía cuando cambia el workload, y cuánto de ese ajuste depende de intervención humana.

**Por qué se mide así:** la velocidad de reacción entre capas es, según los reportes públicos consultados, uno de los puntos más asociados a stranded capacity. Un ajuste lento —o dependiente de una persona— deja capacidad varada durante todo el tiempo que tarda la coordinación en producirse.

### Preguntas

#### P1 — Latencia de cooling

> ¿Aproximadamente cuánto tiempo tarda en ajustarse el cooling tras un cambio significativo de carga de trabajo?

**Tipo de variable:** numérica, escala de razón —minutos, cero absoluto real—.

**Formato de captura:** input numérico con selector de unidad, o slider con marcas de referencia: 5 min / 1 h / 4 h / 1 día.

#### P2 — Latencia de energía

> ¿Y la asignación de energía/potencia frente a ese mismo cambio de carga?

**Tipo de variable:** numérica, escala de razón —minutos—. Mismo formato que P1.

#### P3 — Grado de automatización

> ¿Ese ajuste requiere que una persona lo note y actúe, o está automatizado sin intervención?

**Tipo de variable:** categórica ordinal, cuatro niveles.

### Normalización

#### P1 y P2 —minutos → score—

| Minutos | Score |
|---|---:|
| 0-5 | 100 |
| 6-60 | 75 |
| 61-240 —1-4 h— | 50 |
| 241-1440 —4-24 h— | 25 |
| >1440 —más de 1 día— | 0 |

#### P3 —categoría → score—

| Respuesta | Score |
|---|---:|
| Automatizado, sin intervención humana | 100 |
| Alertas automáticas, acción manual | 67 |
| Reporte periódico + revisión manual | 33 |
| No hay proceso definido | 0 |

Se almacena el valor crudo —minutos exactos y categoría elegida— junto al score normalizado.

### Construcción del índice

```text
score_latencia_coordinación = (score_P1 + score_P2 + score_P3) / 3
```

Promedio simple, sin ponderación diferenciada entre preguntas —ver 2.3 y 2.4 sobre por qué se parte de lineal/parejo—.

### Calibración contra dato de mercado

La distribución del dataset sintético para esta dimensión se sesga hacia scores bajos-medios —media aproximada 35-40/100—, reflejando que los reportes públicos consultados señalan reacción lenta como lo más común en la industria —PUE estancado y alta incidencia de fallas de energía—, reservando los scores altos para operadores de punta —equivalentes a los líderes del sector en eficiencia, por ejemplo PUE ~1.09 vs. promedio 1.54—.

**Fuentes consultadas para esta dimensión:**

- **Uptime Institute — Global Data Center Survey 2025/2026:** PUE promedio 1.54, estancado seis años; 45 % de incidentes graves por causas de energía; adopción de liquid cooling llegando a PUE ~1.05 en los más avanzados.
- **Google Data Centers:** PUE fleet-wide 2025 de 1.09, como referencia de cuartil superior real.

---

## 4. Visibilidad cross-layer

**Qué mide:** si el operador tiene una vista unificada de energía, cooling y workload, o si cada capa se gestiona y monitorea de forma aislada, sin cruce entre equipos.

**Por qué se mide así:** los reportes de mercado consultados confirman este problema como estructural. Los equipos de facilities suelen monitorear energía/cooling mientras IT monitorea servidores/aplicaciones, y «estas vistas rara vez convergen».

Gartner proyecta que recién para 2027 el 75 % de la infraestructura de data centers empresarial va a requerir herramientas de visibilidad en tiempo real, lo que implica que hoy la mayoría todavía no las tiene. El mercado de DCIM —las herramientas que resuelven justamente esto— todavía está en expansión acelerada, con aproximadamente 18-19 % de CAGR anual, señal de que la adopción está lejos de ser la norma.

### Preguntas

#### P1 — Fragmentación de herramientas

> ¿Cuántas herramientas o sistemas distintos usan hoy para monitorear energía, cooling y workload respectivamente?

**Tipo de variable:** numérica, escala de razón —cantidad de sistemas—.

#### P2 — Frecuencia de consolidación

> ¿Con qué frecuencia se cruza o consolida la información de las tres capas en un mismo reporte o vista?

**Tipo de variable:** categórica ordinal, cinco niveles.

#### P3 — Acceso a la vista unificada

> ¿Quién puede ver energía, cooling y workload juntos, en un mismo lugar, dentro de tu organización?

**Tipo de variable:** categórica ordinal, tres niveles.

### Normalización

#### P1 —cantidad de sistemas → score—

| Sistemas usados | Score |
|---|---:|
| 1 —plataforma unificada— | 100 |
| 2 | 67 |
| 3 —uno por capa— | 33 |
| Más de 3, o sin sistema definido | 0 |

#### P2 —frecuencia de consolidación → score—

| Respuesta | Score |
|---|---:|
| Tiempo real / continuo | 100 |
| Diario | 75 |
| Semanal | 50 |
| Mensual o más espaciado | 25 |
| Nunca se cruza la información | 0 |

#### P3 —acceso a vista unificada → score—

| Respuesta | Score |
|---|---:|
| Cualquier responsable puede verlas juntas en un solo lugar | 100 |
| Solo un rol específico las consolida manualmente para reportar | 50 |
| Cada equipo ve solo su capa; nadie tiene la vista completa | 0 |

Se almacena el valor crudo —cantidad exacta de sistemas y categoría elegida en P2 y P3— junto al score normalizado.

### Construcción del índice

```text
score_visibilidad_cross_layer = (score_P1 + score_P2 + score_P3) / 3
```

Promedio simple, mismo criterio lineal documentado en la sección 2.3.

### Calibración contra dato de mercado

Distribución sintética sesgada hacia scores bajos-medios —media aproximada 30-40/100—, reflejando que la fragmentación entre capas es la norma reportada en el mercado, no la excepción, y que la adopción de herramientas de visibilidad unificada —DCIM— todavía está en fase de expansión, lejos de la saturación.

**Fuentes consultadas para esta dimensión:**

- **Gartner Peer Insights / proyección DCIM:** 75 % de la infraestructura de data centers empresarial requerirá herramientas de visibilidad en tiempo real para 2027.
- **Mordor Intelligence / Fortune Business Insights:** tamaño y crecimiento del mercado DCIM —USD 3.5-4B en 2025-2026, CAGR ~18-19 %—.
- **Team Computers / Eptura / NSI1:** reportes sobre silos entre equipos de facilities e IT y su impacto en visibilidad operativa.
- **Schneider Electric Data Center Science Center:** operadores que monitorean PUE de forma continua reducen costos de energía 10-20 % en los primeros dos años de adopción de DCIM —evidencia del valor de la visibilidad unificada—.

---

## 5. Atribución de fricción

**Qué mide:** en cuál de las tres interfaces entre capas —energía↔cooling, cooling↔workload o workload↔energía— percibe el operador que se pierde más capacidad, y qué tan basada en evidencia está esa percepción.

**Por qué se mide así:** no existe un dato de mercado que diga directamente «qué interfaz elige la mayoría» —es una percepción subjetiva por diseño—. Sí hay señales indirectas:

- el cooling representa 30-40 % del consumo eléctrico total de un facility —la carga controlable más grande—;
- muchos servidores operan al 5-15 % de utilización real mientras consumen casi el 100 % de la potencia.

Son dos fuentes de fricción bien documentadas: una del lado energía-cooling y otra del lado workload-energía. Esto se usa solo como referencia débil para calibrar el dataset sintético, no como una verdad de mercado.

### Preguntas

#### P1 — Interfaz de mayor fricción

*Nominal; no entra al índice —ver 2.6—.*

> ¿En cuál de estas interfaces sentís que se pierde más capacidad?

**Opciones:**

- Energía ↔ Cooling
- Cooling ↔ Workload
- Workload ↔ Energía
- No sabría decir

**Tipo de variable:** categórica nominal. Se guarda como dato diagnóstico para el motor de interpretación. El caso borde de P2/P3 se detalla más abajo, junto a su normalización.

#### P2 — Respaldo de la atribución

*Ordinal; entra al índice.*

> ¿Existe algún reporte, log o medición concreta que respalde esta atribución, o es una apreciación sin evidencia registrada?

**Tipo de variable:** categórica ordinal, tres niveles.

> **Nota de diseño —revisión de auditoría—:** la versión anterior pedía autoevaluar «qué tan basada en datos» está la percepción propia, lo que reproduce el mismo sesgo de exceso de confianza que se corrigió en Auto-cuantificación —sección 6—. Se reformuló para preguntar por la existencia de un artefacto concreto —reporte, log o medición—, que es más verificable que una autocalificación de rigor.

#### P3 — Vigencia de la atribución

*Ordinal; entra al índice.*

> ¿Con qué frecuencia revisan o actualizan esta atribución, en vez de asumirla fija desde hace tiempo?

**Tipo de variable:** categórica ordinal, tres niveles.

### Normalización

#### P2 —respaldo → score—

| Respuesta | Score |
|---|---:|
| Sí, con reporte o medición concreta | 100 |
| Solo una estimación aproximada, sin registro formal | 50 |
| No, es una apreciación sin evidencia registrada | 0 |

#### P3 —vigencia → score—

| Respuesta | Score |
|---|---:|
| Se revisa activamente con cada cambio relevante de infraestructura o workload | 100 |
| Se revisa periódicamente —por ejemplo, anual— | 50 |
| Nunca se revisó desde que se formó la percepción inicial | 0 |

Se almacena P1 tal cual —categoría elegida— como dato diagnóstico, independiente del score.

**Caso borde:** si en P1 se elige «No sabría decir», P2 y P3 se registran automáticamente en 0. No tiene sentido preguntar por el respaldo o la vigencia de una atribución que la persona dice no tener.

### Construcción del índice

```text
score_atribución_fricción = (score_P2 + score_P3) / 2
```

P1 no participa del promedio —ver 2.6—. Se usa directamente en el motor de interpretación para redactar cuál es la «fricción principal» del operador.

### Calibración contra dato de mercado

La elección de interfaz —P1— en el dataset sintético se sesga levemente hacia:

- **Energía ↔ Cooling**, por ser la de mayor consumo/controlabilidad documentada;
- **Workload ↔ Energía**, por la subutilización de servidores reportada.

Se deja **Cooling ↔ Workload** con menor frecuencia. Esto es un supuesto débil, documentado como tal, no una proporción verificada en campo.

El score de madurez —P2 + P3— se sesga hacia valores bajos-medios, dado que no hay evidencia de que las empresas midan esto con rigor de forma generalizada.

---

## 6. Auto-cuantificación

**Qué mide:** si el operador sabe, en números concretos, cuánta capacidad tiene varada, o si no tiene forma de cuantificarlo.

> **Precisión importante:** esta dimensión mide la **capacidad de auto-cuantificar** —si la organización puede producir un número coherente—, no la exactitud de ese número. Dos operadores que reporten cifras muy distintas de capacidad varada —una plausible y otra optimista— obtienen el mismo score si ambos completaron P1/P2 de forma coherente. El score evalúa la práctica de medir, no si el resultado medido es correcto. No se renombra la dimensión porque su nombre viene textual del brief del proyecto.

**Por qué se mide así:** esta es la dimensión con el respaldo de mercado más directo y contundente de las cinco. Múltiples fuentes coinciden en que la mayoría de los operadores no sabe si tiene capacidad varada, y mucho menos cuánta: «la mayoría de las veces ni siquiera sabés si tenés capacidad varada o, si la tenés, cuánta hay».

El caso más citado: Uptime Institute encontró que instalaciones que declaran estar al 100 % de su capacidad, tras un análisis de post-optimización, en realidad tenían un 20-25 % de capacidad adicional disponible sin que nadie lo supiera.

**Nota de diseño —revisión posterior—:** la primera versión de esta dimensión pedía que el operador se autoevaluara —«¿tenés una medición precisa o aproximada?»—, lo cual reintroduce el mismo sesgo de exceso de confianza que la dimensión intenta medir. Alguien puede creer que mide bien sin medir bien. Se corrigió pidiendo los números crudos necesarios para que el sistema calcule el porcentaje varado, en vez de pedirle a la persona que se autocalifique.

### Preguntas

#### P1 — Capacidad instalada total

*Numérica; entra al cálculo derivado.*

> ¿Cuál es la capacidad instalada total de tu facility?

**Tipo de variable:** numérica, escala de razón.

**Formato de captura:** un único selector de unidad —MW o kW— que aplica a P1 y P2 en conjunto, no una unidad libre por pregunta. Esto evita que el cálculo derivado se rompa por inconsistencia de unidades —por ejemplo, alguien respondiendo P1 en MW y P2 en kW—.

#### P2 — Capacidad máxima utilizable hoy de forma segura

*Numérica; entra al cálculo derivado.*

> ¿Cuál es la capacidad máxima que podés usar hoy sin arriesgar estabilidad térmica/eléctrica?

**Tipo de variable:** numérica, escala de razón. Misma unidad que P1.

#### P3 — Frecuencia de remedición

*Ordinal; entra al índice.*

> ¿Con qué frecuencia se vuelve a medir este número?

**Tipo de variable:** categórica ordinal, cuatro niveles.

### Dato derivado —calculado por el motor, no autorreportado—

```text
% capacidad varada = (P1 - P2) / P1 × 100
```

**Validación mínima inline:** dado que no hay Motor de validación completo en el MVP —ese motor está descrito en la sección 5 del backlog técnico, fuera de scope—, P2 debe ser menor o igual que P1, y ambos deben ser positivos.

Si no se cumple, el par de respuestas se descarta para el cálculo derivado y se trata como si no se hubiera provisto —score_A = 0 más abajo—.

Este porcentaje se guarda como dato de contexto para el output personalizado. Ejemplo: «tu capacidad varada calculada es de 12 %, el promedio detectado en la industria post-auditoría es 20-25 %».

No participa directamente del score de madurez. No es «mejor o peor» tener un porcentaje más alto o más bajo por sí solo; lo que se evalúa es si la persona pudo proveerlo de forma coherente.

### Normalización

#### Completitud y coherencia de P1 + P2

*Derivado; no autorreportado.*

| Condición | Score |
|---|---:|
| P1 y P2 completos, numéricos, con P2 ≤ P1 | 100 |
| Incompletos, no numéricos, o P2 > P1 —inconsistente— | 0 |

#### P3 —frecuencia de remedición → score—

| Respuesta | Score |
|---|---:|
| Continuamente / en tiempo real | 100 |
| Trimestral o semestral | 67 |
| Anual | 33 |
| Nunca se remidió | 0 |

### Construcción del índice

```text
score_auto_cuantificación = (score_completitud_P1P2 + score_P3) / 2
```

El porcentaje de capacidad varada calculado —P1, P2— se guarda como dato de contexto, no como parte del score.

### Calibración contra dato de mercado

Distribución sintética fuertemente sesgada hacia scores bajos —media aproximada 20-30/100—, en línea con la evidencia de que la falta de cuantificación es la norma reportada, no la excepción.

En el dataset sintético, una proporción alta de «operadores» simulados no completa P1/P2 de forma coherente. Para los que sí completan ambos valores, el porcentaje de capacidad varada derivado se genera con una media cercana al 20-25 % real detectado por Uptime Institute, con dispersión razonable alrededor de ese valor.

---

## 7. Bloqueantes

**Qué mide:** si el operador supiera exactamente dónde está el problema de coordinación, qué le impediría resolverlo —presupuesto, política interna, herramientas o personal capacitado—.

**Por qué se mide así:** hay datos de mercado —de gestión de datos/IT en general, no específicos de data centers, pero aplicables por analogía— que confirman que estos bloqueantes son reales y frecuentes:

- 50 % de los ejecutivos cita restricciones de presupuesto como la principal barrera para convertir datos en valor —Capgemini—;
- 68 % de las organizaciones cita los silos organizacionales como su principal preocupación —Dataversity 2024—;
- la falta de skills/talento es la barrera más citada para operaciones de IT efectivas —Ivanti—.

### Preguntas

#### P1 — Identificación de bloqueantes

*Nominal, multi-selección; no entra al índice —ver 2.6—.*

> Si supieras exactamente dónde está tu problema de coordinación, ¿qué te impediría resolverlo hoy? Podés marcar más de uno.

**Opciones:**

- Presupuesto
- Falta de autoridad o decisión política interna
- Falta de herramientas técnicas
- Falta de personal capacitado
- Nada, podríamos resolverlo

**Tipo de variable:** categórica nominal, multi-selección.

#### P2 — Severidad percibida

*Ordinal; entra al índice.*

> ¿Qué tan severo considerás ese bloqueante para resolver el problema en los próximos 6-12 meses?

**Tipo de variable:** categórica ordinal, cuatro niveles.

### Normalización

#### Cantidad de bloqueantes marcados en P1

*Derivado; entra al índice.*

| Cantidad marcada | Score |
|---|---:|
| 0 —solo «Nada, podríamos resolverlo»— | 100 |
| 1 | 67 |
| 2 | 33 |
| 3 o más | 0 |

#### P2 —severidad → score—

| Respuesta | Score |
|---|---:|
| No es un bloqueante real, podríamos resolverlo si quisiéramos | 100 |
| Obstáculo moderado, resoluble con esfuerzo | 67 |
| Obstáculo fuerte, poco probable resolverlo en el corto plazo | 33 |
| Bloqueante estructural, no lo vemos resoluble en el corto plazo | 0 |

Se almacenan las categorías exactas marcadas en P1 como dato diagnóstico para el motor de interpretación. Ejemplo: «tu principal bloqueante parece ser presupuesto».

**Caso borde:** si en P1 se elige únicamente «Nada, podríamos resolverlo», P2 se autoasigna 100 directamente y no se le pregunta a la persona —no hay bloqueante que calificar en severidad—.

### Construcción del índice

```text
score_bloqueantes = (score_cantidad_P1 + score_P2) / 2
```

### Calibración contra dato de mercado

La distribución sintética de P1 se calibra con:

- más peso en **Presupuesto** —aproximadamente 45-50 % de frecuencia—;
- **Falta de autoridad/política interna** —aproximadamente 35-40 %—;
- algo menos en **Falta de herramientas** y **Falta de personal capacitado**;
- muy baja frecuencia en **Nada, podríamos resolverlo**.

Esto sigue la proporción reportada en las fuentes de gestión de datos/IT citadas arriba. Es una analogía de otro sector —gestión de datos en general—, no un dato específico de data centers, y se documenta como tal.

**Fuentes consultadas para estas tres dimensiones:**

- Cooling como 30-40 % del consumo eléctrico total del facility; utilización real de servidores de 5-15 % pese a consumo casi pleno.
- **Uptime Institute:** facilities que declaran 100 % de capacidad y post-optimización revela 20-25 % adicional disponible; «la mayoría de las veces no se sabe si hay capacidad varada o cuánta».
- **Capgemini:** 50 % de ejecutivos cita restricciones de presupuesto como principal barrera.
- **Dataversity 2024 Trends in Data Management Survey:** 68 % cita silos organizacionales como principal preocupación.
- **Ivanti:** falta de skills/talento como barrera más citada para operaciones de IT efectivas.

---

## 8. Datos de segmentación —contexto del operador—

**Qué es:** a diferencia de las cinco dimensiones —que miden madurez—, estos son dos o tres campos de metadata sobre el operador, sin dirección de mejor/peor.

Sirven para uso futuro —comparación por grupos comparables—. No se usan en el MVP para segmentar nada; se capturan ahora para no tener que volver a pedirlos después.

### Campos

- **Tamaño aproximado del facility —categórico—:** `<1 MW` / `1-5 MW` / `5-20 MW` / `>20 MW`.
- **Región —categórico—:** continente o región amplia, no país exacto, para no comprometer el anonimato.
- **Tipo de data center —categórico—:** hyperscale / colocation / enterprise / edge.

### Decisión de scope

El Motor de grupos comparables —que usaría estos campos para segmentar la comparación— queda fuera del scope definitivo. El brief de No Country solo pide «posición relativa en la industria» en general, no por segmento.

Se capturan los campos igualmente, sin costo relevante de tiempo, para dejar la puerta abierta a una mejora futura sin tener que volver a pedirle datos a nadie.

Estos mismos tres campos se agregan como columnas al dataset público sintético —sección 2.7—, para que estén disponibles el día que se decida usarlos.

## 9. Motor de rebalanceo —fórmula definitiva—

Los factores que ya estaban documentados —cantidad de respuestas válidas, calidad de datos, representatividad de la muestra y actualidad— se traducen en una fórmula concreta:

```text
peso_primario = (n_válido / (n_válido + k)) × factor_diversidad
peso_público = 1 - peso_primario
```

### Variables

- **n_válido:** cantidad de respuestas primarias que pasan los chequeos mínimos de completitud/coherencia ya definidos por dimensión —por ejemplo, el chequeo P2 ≤ P1 de Auto-cuantificación, sección 6—. Reemplaza «calidad de datos»: una respuesta que no pasa el chequeo no cuenta para el peso.

- **k:** constante de suavizado, documentada como supuesto de diseño. Propuesta inicial: `k = 50`. Con 50 respuestas válidas el peso primario ronda 50 %; con 200 ronda aproximadamente 80 %. Es ajustable sin cambiar la lógica.

- **factor_diversidad:** proporción de categorías distintas cubiertas entre las respuestas primarias válidas, sobre el total de categorías posibles en los tres campos de segmentación —sección 8—. Es un valor entre 0 y 1.

  Reemplaza «representatividad de la muestra». Si todas las respuestas primarias vienen del mismo tipo/tamaño/región, este factor es bajo y frena el crecimiento del peso primario aunque `n_válido` sea alto. Es una protección contra el sesgo de auto-selección discutido anteriormente.

- **Caso borde:** si `n_válido = 0`, `factor_diversidad` se define como 0, por lo que `peso_primario = 0` automáticamente —100 % público—.

- **Actualidad de la información:** no se implementa en el MVP. Se documenta como mejora futura: ponderar por antigüedad de la respuesta una vez que haya volumen suficiente como para que importe.

### Benchmark combinado

Los percentiles del operador se calculan contra una distribución combinada, mezclando la distribución pública y la primaria según `peso_público` y `peso_primario`, respectivamente.

> **Nota importante —desacopla la fórmula del tamaño del dataset público—:** esta fórmula depende únicamente del volumen y diversidad de las respuestas primarias, nunca del tamaño del dataset público/sintético. Esto significa que la elección del tamaño del dataset sintético —sección 10— es una decisión independiente, que no afecta qué tan rápido crece el peso de los datos reales.

## 10. Tamaño del dataset público sintético

Dado que la fórmula de rebalanceo —sección 9— no depende del tamaño del dataset público, esta decisión es puramente sobre estabilidad estadística del cálculo de percentiles: cuántas filas sintéticas hacen falta para que percentiles y cuartiles no salten de forma rara.

**Decisión:** 1.000 filas sintéticas por dimensión/segmento como default recomendado.

Es más que suficiente para percentiles estables —unos pocos cientos ya alcanzan—, sin ser un número tan grande que parezca, por error, una encuesta real a una porción significativa del universo mundial de data centers —aproximadamente 9.000-12.000 según fuentes públicas—.

Si se prefiere un número mayor —3.000-4.000—, no tiene costo relevante de tiempo generarlo y es igual de válido. La única razón para no ir más grande es mantener la etiqueta de «dataset simulado» fácil de sostener frente a cualquiera que lo revise.

## 11. Amenazas a la validez / límites conocidos

Todo instrumento de medición serio declara explícitamente dónde puede estar equivocado. Estos son los límites conocidos de este benchmark, ya asumidos como parte del diseño para un MVP, no errores a corregir de urgencia:

1. **La calibración inicial se basa en datos sintéticos, no en observaciones de operadores reales.** El dataset público de arranque son simulaciones calibradas con reportes públicos generales, no encuestas reales de estas cinco dimensiones —ver sección 2.7/10—.

2. **Las escalas ordinales usan espaciamiento lineal por ausencia de evidencia empírica para una ponderación diferencial**, no porque se haya comprobado que las distancias entre niveles son iguales —ver sección 2.3/2.4—.

3. **Todas las preguntas de un índice pesan igual dentro de su dimensión** —promedio simple, no ponderado—. No hay evidencia de que, por ejemplo, automatización explique la madurez de Latencia en la misma proporción que la velocidad de ajuste en minutos. Es un supuesto de partida, documentado como tal.

4. **El benchmark mide capacidad organizacional autorreportada, no desempeño verificado.** No audita si las prácticas declaradas se ejecutan realmente, solo si la organización reporta poder observarlas y actuar sobre ellas.

5. **Los percentiles son inestables en las primeras etapas de adopción.** Si las primeras respuestas primarias vienen de un tipo de operador poco representativo —por ejemplo, mayoría hyperscalers—, el percentil de los primeros usuarios puede no ser comparable al que reciban usuarios posteriores cuando la muestra se diversifique. El factor de diversidad de la fórmula de rebalanceo —sección 9— mitiga parte de este riesgo, pero no lo elimina. Los percentiles de las primeras semanas deben tratarse como experimentales.

6. **La independencia entre dimensiones no está probada.** Es esperable que, por ejemplo, buena Visibilidad correlacione con buena Auto-cuantificación. Son capacidades relacionadas, no independientes. Se evaluará empíricamente cuando haya volumen suficiente de respuestas primarias.

7. **Bloqueantes mezcla madurez organizacional con acceso a recursos externos**, por ejemplo presupuesto. Una organización madura sin presupuesto puede obtener un score bajo en esta dimensión por razones ajenas a su nivel de coordinación. Es la dimensión con mayor riesgo de contaminación del constructo, marcada así a propósito, no corregida, porque el brief la pide tal como está planteada.

8. **El modelo prioriza interpretabilidad y trazabilidad de las decisiones sobre optimización estadística en esta fase.** Cada elección de score está documentada y es auditable, a costa de no ser la más precisa posible.

Exponer estas limitaciones no debilita el instrumento: deja claro qué puede sostener el benchmark hoy y qué queda para cuando haya datos reales suficientes.

## 12. Estado del documento

Las cinco dimensiones del benchmark, los datos de segmentación y el motor de rebalanceo están cerrados con su formato completo.

**Próximo paso:** script de generación del dataset sintético y backlog de implementación definitivo —documento aparte, basado en la guía de arquitectura, anotando qué queda dentro y fuera del scope—.

---

*Benchmark de Madurez en Data Centers — Documento Metodológico*
