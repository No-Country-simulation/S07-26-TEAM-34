# Reglas core del benchmark — carga siempre

## Misión
Motor determinista y privado: respuestas anónimas → scores por dimensión → percentiles → perfil de fricción → comparación top 25%.

## Reglas no negociables
- El LLM NO calcula scores, percentiles, cuartiles, pesos ni agregados.
- Validación es compuerta de entrada: respuesta inválida no alimenta scores ni dataset.
- Sin score general único en el MVP.
- Privacidad y agregación son frontera de persistencia, no filtro posterior.
- No exponer respuestas individuales ni segmentos < umbral mínimo.
- Cada resultado registra versiones metodológicas que lo produjeron.
- El rebalanceo se ejecuta en snapshots offline, nunca durante la solicitud.
- Reglas de scoring, pesos y cohortes en config versionada, no en código ni prompts.

## Motores (8)
`validation` → `scoring` → `cohort` → `benchmark` → `top-quartile` → `rebalancing` → `interpretation` → `privacy-aggregation`

## Rutas
- **Online:** validación → scoring → cohorte → snapshot → percentiles → top25 → interpretación → output
- **Offline (batch):** datos públicos + primarios → calidad → privacidad → rebalanceo → snapshot candidato → backtest → publicación

## Stack de referencia
Ver `docs/01_SYSTEM_ARCHITECTURE.md` para detalle de componentes.
Ver `docs/adr/` para decisiones que no se modifican sin nuevo ADR.

## Spec activa
`.kiro/specs/benchmark-core/` — trabajar siempre contra la spec, no contra los docs largos.
