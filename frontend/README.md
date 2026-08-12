# Frontend — Benchmark de Madurez en Data Centers

Landing + encuesta + resultados. Vite + React + TypeScript + Tailwind CSS.

## Desarrollo local

```bash
cp .env.example .env    # ajustar VITE_API_URL si el backend no corre en localhost:8000
npm install
npm run dev
```

Requiere el backend corriendo (`app/main.py` del repo, ver README raíz) — el formulario
se construye dinámicamente contra `GET /api/v1/questionnaire`, así que cualquier cambio
en `config/questionnaire.yaml` se refleja acá sin tocar código.

## Estructura

- `src/components/` — Hero, HowItWorks, y las secciones de encuesta (`survey/`) y
  resultados (`results/`).
- `src/lib/questionnaire.ts` — indexa la respuesta de `/questionnaire` por dimensión
  y extrae los ids cortos (`p1`/`p2`/`p3`), con la misma convención que
  `app/config/loader.py` del backend.
- `src/lib/formState.ts` — estado del formulario y su conversión al payload exacto
  de `POST /respuestas`, incluyendo los casos borde documentados (atribución
  `no_sabria_decir`, bloqueantes `nada`).
- `src/api.ts` / `src/types.ts` — cliente HTTP y tipos alineados a
  `app/schemas/request.py` / `response.py`.

## Deploy

Pensado para Vercel: build estático (`npm run build` → `dist/`), sin SSR.
Configurar `VITE_API_URL` como variable de entorno en el proyecto de Vercel apuntando
al backend desplegado (Render).
