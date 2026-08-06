# Backlog Definitivo — Motor del Benchmark de Madurez en Data Centers

> **Benchmark de madurez · Data Centers**
>
> Basado en la guía de arquitectura inicial, revisado y anotado contra lo que pide el brief de No Country y contra el documento metodológico de las 5 dimensiones. Cada bloque indica su estado: **[SCOPE DEFINITIVO]** o **[FUERA DE SCOPE]**.

## 1. Qué estamos construyendo

El proyecto es un sistema que recibe las respuestas de un operador de data center, las transforma en puntuaciones, calcula su posición frente a otros operadores y genera un diagnóstico personalizado.

```text
Operador responde el formulario
            ↓
Se convierten en puntuaciones
            ↓
Se compara con el benchmark (público + primario, según rebalanceo)
            ↓
Se identifica la principal fricción
            ↓
Se compara con el 25 % superior
            ↓
Se genera el resultado y el JSON para el PDF
            ↓
La respuesta anónima se agrega al dataset primario
```

**Idea central:** los motores calculan de forma determinística; el LLM solo redacta el texto final a partir de esos cálculos ya hechos.

## 2. Qué es un motor

Un motor es un módulo de código que recibe datos, aplica reglas y devuelve un resultado específico. No son modelos de IA — son funciones de Python, reglas de negocio y cálculos estadísticos.

> *Nombre a discutir más adelante si "motor" no convence — se mantiene por ahora para no reabrir esa discusión en medio del backlog.*

```python
SCORES = {
    "automatic": 100,
    "minutes": 67,
    "less_than_hour": 50,
    "hours": 33,
    "more_than_day": 0,
}


def score_answer(answer: str) -> int:
    return SCORES[answer]
```

Las preguntas, pesos y puntuaciones viven en archivos de configuración versionados (ver sección 9) — nunca ocultas dentro de un prompt.

## 3. Motores del scope definitivo

*Ordenados según se van a construir (ver también sección 12).*

### 3.1. Motor de scoring — **[SCOPE DEFINITIVO]**

Convierte respuestas en puntuaciones. Implementa las 5 dimensiones tal como quedaron especificadas en el documento metodológico: preguntas, tipo de variable, normalización y construcción del índice por dimensión.

- **Salida principal:** scores por pregunta y por dimensión (0-100 cada una).

### 3.2. Motor de grupos comparables — **[SCOPE DEFINITIVO]**

Selecciona el grupo de operadores adecuado para la comparación, usando los 3 campos de contexto: tamaño, región y tipo de data center (documento metodológico, sección 8).

- Agrupa por región / tamaño del facility / tipo de data center.
- **Salida principal:** grupo global y grupo comparable, con su tamaño de muestra.

> **Nota de implementación:** en el dataset público sintético ya hay volumen suficiente por segmento (1.000 filas repartidas). En las respuestas primarias reales, al principio va a haber pocos o ningún dato por segmento — en ese caso el motor debe poder devolver el grupo global como respaldo, no fallar.

### 3.3. Motor de rebalanceo — **[SCOPE DEFINITIVO]**

Mezcla progresivamente datos públicos y datos primarios según la fórmula definida en el documento metodológico (sección 9):

```text
peso_primario = (n_válido / (n_válido + k)) × factor_diversidad
```

- No solo calcula los pesos: **reconstruye la distribución combinada** (pública + primaria, ponderada) que el Motor de benchmark y percentiles (3.4) va a usar — no es responsabilidad de 3.4 rearmar esa mezcla.
- **Salida principal:** peso público, peso primario y distribución combinada ya reconstruida.

### 3.4. Motor de benchmark y percentiles — **[SCOPE DEFINITIVO]**

Calcula la posición relativa del operador contra la distribución combinada, dentro de su grupo comparable.

- Distribuciones, mediana y cuartiles (no promedio — estadística robusta).
- Percentil por dimensión.
- **Salida principal:** percentiles y estadísticas de referencia.

### 3.5. Motor de comparación con el cuartil superior — **[SCOPE DEFINITIVO]**

Analiza qué hace diferente el 25 % superior, dentro del mismo grupo comparable.

- Selecciona operadores desde el percentil 75.
- Compara sus respuestas con las del nuevo operador, dimensión por dimensión.
- **Salida principal:** brechas concretas contra el top 25 %.

### 3.6. Motor de interpretación — **[SCOPE DEFINITIVO]**

Convierte los resultados numéricos en un perfil y texto personalizado. Es la única pieza donde entra el LLM, y solo para redactar — nunca para calcular scores, percentiles o pesos.

- **El perfil cualitativo lo asigna una regla determinística en Python** (umbrales sobre los scores por dimensión; por ejemplo, "operación reactiva" si Latencia y Visibilidad quedan bajo cierto puntaje). El LLM nunca inventa ni elige el perfil: solo lo recibe ya calculado y lo explica en prosa.
- Fricción principal y comparación con el cuartil superior en lenguaje natural.
- **Salida principal:** resultado estructurado para web, PDF y como input del LLM.

### 3.7. Motor de privacidad y agregación (versión liviana) — **[SCOPE DEFINITIVO, RECORTADO]**

Evita exponer información individual. **No implica login ni credenciales de ningún tipo** — el benchmark es anónimo por diseño, no hay cuentas de operador.

- Genera un ID aleatorio (UUID) por respuesta, sin relación con nombre, email, empresa o IP.
- El formulario nunca captura datos identificables en primer lugar — no hay nada que encriptar porque no hay PII que entre al sistema.
- **Salida principal:** datos anonimizados y estadísticas agregadas.

> *Recortado respecto a la versión original: sin supresión de grupos pequeños ni auditoría de accesos/cambios — quedan pendientes de revisar más adelante. Este motor no se puede sacar del todo: el brief lo pide explícitamente como criterio de éxito ("sin exponer datos individuales").*

## 4. Fuera del scope definitivo

### 4.1. Motor de validación — **[FUERA DE SCOPE]**

Revisaría completitud, contradicciones y duplicados de cada respuesta. No lo pide el brief. Las validaciones mínimas indispensables —por ejemplo, coherencia P1/P2 en Auto-cuantificación— quedan como chequeos livianos dentro de cada motor que los necesita, no como motor aparte.

## 5. Qué tendrá el proyecto además de los motores

| Componente | Función |
|---|---|
| Formulario web | Permite que el operador complete el diagnóstico en menos de 10 minutos. |
| API backend | Recibe las respuestas, ejecuta los motores y devuelve resultados. |
| Base de datos | Guarda preguntas, versiones, respuestas anónimas, scores, percentiles y auditoría. |
| Dataset público inicial | Sirve como referencia mientras todavía no existen suficientes respuestas propias. |
| Dataset primario | Se forma con respuestas validadas y se convierte gradualmente en la fuente principal. |
| Servicio de resultados y PDF | Entrega un JSON estable para mostrar el diagnóstico y generar el informe. |
| Testing y versionado | Testing de código —casos normales y extremos por motor— y control de versiones en GitHub. Es una práctica estándar de desarrollo, no un motor ni un componente separado. |

## 6. Cómo se construye cada motor

1. Definir una sola responsabilidad.
2. Definir claramente la entrada.
3. Escribir las reglas o cálculos, siguiendo la normalización documentada por dimensión.
4. Definir una salida estructurada.
5. Probar con casos normales y extremos. Los casos borde ya están documentados por dimensión — testing de código normal, no un motor aparte.
6. Registrar la versión de las reglas en el archivo de configuración, versionado en Git — control de versiones estándar, tampoco un motor aparte.

## 7. Dónde entra el LLM

El LLM es una capa de apoyo, nunca reemplaza el cálculo:

- Redacta el diagnóstico en lenguaje natural (Motor de interpretación, 3.6).
- No calcula scores, percentiles, cuartiles ni pesos del rebalanceo — eso lo hacen los motores determinísticos.
- Sus prompts viven en archivos separados del código (ver `prompts/` en la sección 9), nunca hardcodeados dentro de una función.

## 8. Arquitectura del scope definitivo

```text
Formulario (cuestionario + 3 campos de contexto)
            ↓
API backend
            ↓
Scoring (3.1)
            ↓
Grupos comparables (3.2)
            ↓
Rebalanceo (3.3) → Benchmark y percentiles (3.4)
            ↓
Comparación top 25 % (3.5)
            ↓
Interpretación con LLM (3.6)
            ↓
Resultado web / JSON para PDF

Respuesta validada → Privacidad y agregación (3.7) → Dataset primario
```

## 9. Estructura del repositorio

*Cada carpeta con su propósito explícito — para no dejar nada sin justificar.*

> Algunas líneas del árbol aparecían truncadas horizontalmente en el PDF original; se indican con `…`.

```text
app/
├── api/
│   ├── questionnaire.py   # expone las preguntas/opciones vigentes al formulario
│   ├── responses.py       # recibe las respuestas completadas de un operador
│   ├── results.py         # devuelve el resultado calculado, para mostrar en la web
│   └── pdf_input.py       # arma el JSON específico que consume Proyecto 5 (formato distin…)
├── engines/
│   ├── scoring_engine.py
│   ├── peer_group_engine.py
│   ├── rebalance_engine.py
│   ├── benchmark_engine.py
│   ├── top_quartile_engine.py
│   ├── interpretation_engine.py
│   └── privacy_engine.py
├── models/                # entidades: Pregunta, Dimensión, Respuesta, Score, Operador, GrupoCom…
├── repositories/          # capa que guarda/lee de la base de datos, separada del cálculo
├── services/              # orquesta el orden en que se llaman los motores para un pedido comple…
├── prompts/               # plantillas de prompt del LLM, separadas del código (ver sección 7)
└── main.py

tests/
docs/
config/
└── dimensiones.yaml       # preguntas, opciones, pesos y puntuaciones de las 5 dimensiones — ve…
```

**Versionado metodológico:** cada respuesta guardada en la base incluye `benchmark_version` y `dimension_version`, tomados de `config/dimensiones.yaml` al momento de guardar la respuesta. No solo se versiona el código en Git, sino que queda registrado con qué versión de las reglas se calculó cada score histórico. Esto importa el día que cambien una pregunta o un peso: sin esto, no habría forma de saber si una respuesta vieja se calculó con las reglas actuales o con unas anteriores.

> *Si `models/`, `repositories/` y `services/` como carpetas separadas no aportan claridad al equipo, se pueden fusionar en menos carpetas. La separación entre "forma de los datos", "acceso a la base de datos" y "cálculo" (`engines`) es lo importante, no los nombres exactos de las carpetas.*

## 10. Stack tecnológico

| Capa | Elección | Nota |
|---|---|---|
| Backend | **Python + FastAPI** | Consistente con los engines, ya definidos como funciones de Python. |
| Despliegue del backend | **Render** | Solo la API/backend — no la base de datos (ver fila siguiente). |
| Validación de datos | **Pydantic** | Valida el payload de entrada/salida de cada endpoint contra el esquema de `config/dimensiones.yaml`. |
| Base de datos | **PostgreSQL**, en contenedor **Docker**, alojado en **Neon** | Neon en vez de Supabase —pausa proyectos inactivos en el free tier— y en vez de Render free —borra la base a los 90 días—; Neon no expira por inactividad. |
| Frontend | **Next.js**, desplegado en **Vercel** | Vercel es la plataforma de hosting, no el framework. Next.js es lo que efectivamente se construye y despliega ahí. |
| Testing | **pytest** | Casos normales y extremos por motor, ya documentados por dimensión. |
| Control de versiones | **Git** | Reglas/pesos versionados junto con el código, no como práctica aparte. |

### LLM para el Motor de interpretación (3.6)

Todavía sin decidir; candidatas en danza:

- **Ollama:** modelos open source, se pueden correr local/self-hosted, sin costo por request.
- **Gemini:** API de Google.
- **Kimi:** Moonshot AI, modelo chino, mencionado por ser más permisivo/menos restringido.

*A definir con el equipo — no se cerró en esta sesión.*

## 11. Esquema de base de datos

*PostgreSQL. Tres tablas alcanzan para el scope definitivo — sin sobre-normalizar.*

### `operators`

Una fila por cuestionario completado, sintético o real. Es la tabla que separa identidad de respuesta (Motor de privacidad, 3.7).

| Columna | Tipo | Nota |
|---|---|---|
| `id` | `UUID (PK)` | Identificador aleatorio, sin relación con nombre/email/empresa. |
| `source` | `enum(public_synthetic, primary)` | Distingue el dataset público sintético de las respuestas reales. |
| `region` | `text` | Campo de contexto (documento metodológico, sección 8). |
| `facility_size` | `text` | Ídem. |
| `dc_type` | `text` | Ídem. |
| `benchmark_version` | `text` | Versión de `config/dimensiones.yaml` vigente al momento de la respuesta. |
| `dimension_version` | `text` | Ídem, por si se versiona distinto que el benchmark general. |
| `created_at` | `timestamp` |  |

### `dimension_scores`

Una fila por operador y por dimensión —5 filas por operador—. Acá vive el valor crudo junto al score, como pide la sección 2.5 del documento metodológico.

| Columna | Tipo | Nota |
|---|---|---|
| `id` | `serial (PK)` |  |
| `operator_id` | `UUID (FK → operators.id)` |  |
| `dimension` | `enum(visibilidad, atribucion_friccion, latencia, auto_cuantificacion, bloqueantes)` |  |
| `score` | `numeric(5,2)` | 0-100, ya normalizado. |
| `raw_answers` | `jsonb` | Respuestas crudas de esa dimensión: minutos, categoría elegida, etc. |

### `results`

Una fila por operador, con el resultado ya calculado —lo que consumen el endpoint de resultados y el de PDF—. Evita recalcular todo cada vez que alguien vuelve a pedir su reporte.

| Columna | Tipo | Nota |
|---|---|---|
| `operator_id` | `UUID (PK, FK → operators.id)` |  |
| `percentiles` | `jsonb` | Percentil por dimensión, dentro de su grupo comparable. |
| `friccion_principal` | `text` | Dimensión con el percentil relativo más bajo. |
| `profile` | `text` | Perfil cualitativo —regla determinística, Motor de interpretación—. |
| `top_quartile_gaps` | `jsonb` | Brechas concretas contra el cuartil superior por dimensión. |
| `diagnostico_texto` | `text` | Texto redactado por el LLM a partir de los campos anteriores. |
| `computed_at` | `timestamp` |  |

> **Lo que no tiene tabla propia:** el dataset agregado/estadísticas públicas se calculan con consultas SQL sobre `dimension_scores`, filtrando por `source`; no se guardan aparte — evita duplicar datos que ya están en la tabla base.

## 12. Orden recomendado de desarrollo

1. Definir preguntas, opciones, puntuaciones y pesos — ya cerrado en el documento metodológico.
2. Generar el dataset público sintético — ya generado: `dataset_publico_sintetico.csv`.
3. Construir el Motor de scoring con datos ficticios.
4. Construir el Motor de grupos comparables.
5. Construir el Motor de rebalanceo y el Motor de benchmark/percentiles.
6. Construir el Motor de comparación con el top 25 %.
7. Construir la API y la base de datos.
8. Construir el Motor de interpretación —con LLM y prompts en archivo separado— y generar el input del PDF.
9. Implementar el Motor de privacidad y agregación —versión liviana—.

## 13. MVP esperado (idéntico al criterio de éxito del brief)

La primera versión debe poder:

- recibir el formulario —5 dimensiones + 3 campos de contexto—;
- calcular las cinco dimensiones;
- calcular percentiles contra el benchmark combinado —público + primario—, dentro del grupo comparable del operador;
- identificar la principal fricción;
- comparar con el cuartil superior;
- generar un resultado estructurado y específico —no genérico—;
- guardar la respuesta de forma anónima;
- alimentar el dataset primario;
- entregar el JSON para el PDF de Proyecto 5;
- completar todo en menos de 10 minutos de parte del operador.

No necesita Machine Learning ni agentes autónomos. Es núcleo determinista y estadístico, con una sola capa de LLM al final para redactar texto.

---

*Benchmark de Madurez en Data Centers — Backlog Definitivo v3*
