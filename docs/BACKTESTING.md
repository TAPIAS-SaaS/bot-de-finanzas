# Metodología de Backtesting Reproducible (`BACKTESTING.md`)

## 1. Reglas de Ejecución Conservadora

El motor de backtesting (`trading_engine/src/trading_bot/backtesting/__init__.py`) está separado del motor de ejecución en vivo y aplica las siguientes salvaguardas metodológicas:

1. **Ejecución en la apertura de la siguiente vela (`Next-Bar Open`)**: Una señal emitida al cierre de la vela `t` nunca se ejecuta al precio de cierre de `t`, sino al precio `open` de la vela `t + 1` penalizado por el deslizamiento (`DEFAULT_SLIPPAGE_RATE = 0.05%`) y la comisión (`DEFAULT_FEE_RATE = 0.10%`).
2. **Supuesto conservador intravela (Stop vs. Objetivo)**: Si durante una misma vela `1h` el rango `[low, high]` toca tanto el nivel de `stop_loss` como el de `take_profit`, el simulador asume incondicionalmente que **se tocó primero el Stop-Loss**, evitando inflar artificialmente la tasa de aciertos.
3. **Mismo Gestor de Riesgo**: Cada señal de backtest es evaluada por la misma clase `RiskManager` que opera en Paper Trading.

## 2. División Cronológica de Datos (60% / 20% / 20%)

Toda serie histórica se divide cronológicamente sin mezclar observaciones futuras:
- **60% Desarrollo (`development`)**: Calibración inicial de hipótesis.
- **20% Validación (`validation`)**: Verificación intermedia de estabilidad.
- **20% Prueba Final Fuera de Muestra (`out_of_sample`)**: Muestra intacta para evaluar los criterios de aceptación.

## 3. Criterios de Aceptación Fuera de Muestra (OOS)

Para que una estrategia supere el control de evaluación (lo cual sigue sin garantizar beneficios futuros), debe cumplir simultáneamente en el segmento fuera de muestra (`out_of_sample`):
- Rentabilidad neta después de comisiones y deslizamiento `> 0%`.
- `Profit Factor > 1.10`.
- Al menos `50` operaciones cerradas en la muestra de evaluación (si el período contiene menos de 50 operaciones, el sistema emite una advertencia explícita de muestra insuficiente y retiene el estado en simulación).
- Drawdown máximo `<= 5.0%` (compatible con el límite del `RiskManager`).
- Rentabilidad neta positiva incluso bajo una **prueba de estrés de costes (+50% en comisiones)**.
