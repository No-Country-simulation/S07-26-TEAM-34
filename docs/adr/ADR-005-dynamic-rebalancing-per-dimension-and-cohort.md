# ADR-005: Rebalanceo dinámico por dimensión y cohorte

- Estado: Aceptado
- Fecha: 2026-08-03

## Contexto

Un ratio fijo público/primario ignora que la madurez del dataset puede variar entre segmentos y dimensiones.

## Decisión

Calcular el peso primario por dimensión y cohorte usando tamaño efectivo, calidad, representatividad, actualidad y estabilidad. El peso público será el complemento. La función exacta será versionada y validada por backtesting.

## Consecuencias

- Transición más fiel a la evidencia.
- Mayor complejidad metodológica y observabilidad.
- Los pesos deben almacenarse dentro del snapshot.
