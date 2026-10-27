# Gestión de Riesgo Determinista (`RISK_MANAGEMENT.md`)

El módulo `RiskManager` (`trading_engine/src/trading_bot/risk/__init__.py`) es completamente independiente de las estrategias, de Gemini y de TimesFM. Ninguna recomendación de IA puede modificar ni elevar estos límites.

## 1. Límites Iniciales de Diseño

| Parámetro | Valor por Defecto | Variable de Entorno |
| :--- | :--- | :--- |
| Capital inicial simulado | `$400.000 COP` | `INITIAL_CAPITAL_COP` |
| Riesgo máximo previsto por operación | `0,5%` del patrimonio | `MAX_RISK_PER_TRADE=0.005` |
| Exposición bruta máxima | `50,0%` del patrimonio | `MAX_EXPOSURE=0.50` |
| Límite de pérdida diaria | `1,0%` del patrimonio del día | `DAILY_LOSS_LIMIT=0.01` |
| Límite de drawdown acumulado | `5,0%` desde el máximo histórico | `MAX_DRAWDOWN_LIMIT=0.05` |
| Posiciones simultáneas máximas | `1` posición spot | `MAX_CONCURRENT_POSITIONS=1` |
| Valor nocional mínimo de orden | `5,00 USDT` | `MIN_ORDER_NOTIONAL_USDT=5.0` |
| Apalancamiento / Margen / Cortos | **Prohibidos (`false`)** | Restricción fija en código |
| Retiros por API | **Prohibidos (`false`)** | Restricción fija en código |

> **Nota importante**: Los órdenes stop-loss reducen y acotan el riesgo en condiciones normales de liquidez, pero no garantizan un precio exacto de ejecución ante saltos bruscos de mercado (*gaps*).

## 2. Fórmula de Tamaño de Posición y Rechazo por Mínimo del Exchange

1. Se estima el precio real de entrada aplicando deslizamiento: $P_{\text{entry}} = P_{\text{ref}} \times (1 + s)$.
2. Se estima el precio conservador de salida en stop: $P_{\text{stop\_exit}} = P_{\text{stop}} \times (1 - s)$.
3. La pérdida total por unidad (incluyendo comisiones de entrada y salida $f$) es:
   $$L_{\text{unit}} = (P_{\text{entry}} - P_{\text{stop\_exit}}) + (P_{\text{entry}} + P_{\text{stop\_exit}}) \times f$$
4. La cantidad máxima por riesgo es $Q_{\text{risk}} = \frac{\text{Patrimonio} \times 0.005}{L_{\text{unit}}}$, acotada además por la exposición máxima (`50%` del patrimonio).
5. **Regla de rechazo estricto**: Si el valor nocional resultante $Q \times P_{\text{entry}}$ es inferior al mínimo exigido por el exchange (`5,00 USDT`), **el gestor de riesgo nunca incrementa el tamaño de la orden para forzar la entrada**. Rechaza la operación con el código `MIN_NOTIONAL_EXCEEDS_RISK_OR_EXPOSURE`.

## 3. Interruptor de Emergencia (*Kill Switch*)

- Puede activarse manualmente desde la barra superior del Dashboard o la pestaña **Gestor de Riesgo**, o automáticamente ante incumplimiento de límites.
- Cuando está activo, bloquea toda nueva orden de entrada (`KILL_SWITCH_ACTIVE`) permitiendo únicamente salidas protectoras (`SELL`).
- Para desactivarlo se exige revisar los registros y enviar la frase explícita de confirmación `CONFIRMO_REVISION_DE_REGISTROS`.
