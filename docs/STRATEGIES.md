# Especificación de Estrategias (`STRATEGIES.md`)

Todas las estrategias implementan la interfaz `BaseStrategy` en `trading_engine/src/trading_bot/strategies/__init__.py`, evalúan exclusivamente velas cerradas (`is_closed=True`) y devuelven un objeto `StrategySignal` tipado. Ninguna señal equivale a una orden ejecutada: toda señal `BUY` pasa por el `RiskManager`.

## 1. Alineación Temporal sin Sesgo de Anticipación (*No Look-Ahead Bias*)

La función `align_4h_to_1h_without_lookahead(candles_1h, candles_4h, decision_close_ts)` garantiza que cuando se toma una decisión al cierre de una vela de `1h` (por ejemplo, a las `14:00 UTC`), el filtro de tendencia de `4h` solo pueda observar velas de `4h` cuyo `close_timestamp` sea `<= 14:00 UTC` (es decir, la vela cerrada a las `12:00 UTC`, nunca la vela de `12:00–16:00 UTC` que sigue en formación).

## 2. Estrategia A: Seguimiento de Tendencia (`trend_following_v1`)

- **Filtro de tendencia macro (4h)**: `EMA(50) > EMA(200)`.
- **Indicadores de entrada (1h)**: `EMA(20) > EMA(50)` y `Close(1h) > EMA(20)`.
- **Filtro de volumen y volatilidad**: Volumen relativo de 20 períodos `>= 0.90x` y ratio `ATR(14) / Close` entre `0.20%` y `3.50%`.
- **Stop-Loss propuesto**: `Close - 2.0 * ATR(14)`.
- **Take-Profit propuesto**: `Close + 3.5 * ATR(14)`.
- **Regla de salida adicional**: Cierre de vela `1h` por debajo de `EMA(50)` o pérdida del filtro `EMA(50) > EMA(200)` en `4h`.

## 3. Estrategia B: Reversión a la Media (`mean_reversion_v1`)

- **Indicadores (1h)**: Bandas de Bollinger de 20 períodos (`±2.0 σ`) y puntuación `Z-Score`.
- **Restricción contra tendencia fuerte**: Se bloquean compras si el spread `(EMA50_4h - EMA200_4h) / EMA200_4h` es inferior a `-1.5%` (tendencia bajista fuerte en 4h) o si `ATR(14) / Close > 3.0%`.
- **Condición de entrada**: `Z-Score <= -1.85` al cierre de la vela `1h`.
- **Stop-Loss propuesto**: `Close - 1.8 * ATR(14)`.
- **Condición de salida**: Retorno a la media móvil de 20 períodos (`Close >= Media_20` o `Z-Score >= 0.15`).

## 4. Estrategia C: Ruptura de Rangos (`range_breakout_v1`)

- **Indicadores (1h)**: Canal de Donchian calculado sobre las **20 velas cerradas anteriores** a la vela actual (`upper`, `lower`, `mid`), `ATR(14)` y Volumen Relativo de 20 períodos.
- **Condición de entrada**: `Close(1h) > Donchian_High(20)` acompañado de `Volumen_Relativo >= 1.25x`.
- **Stop-Loss propuesto**: `max(Donchian_Mid, Close - 2.0 * ATR(14))` (ajustado a `Close - 1.5 * ATR(14)` si el punto medio superara el cierre).
- **Condición de salida**: Cierre de vela `1h` por debajo del punto medio del canal (`Donchian_Mid`) o alcance de objetivo `+3.2 * ATR(14)`.
