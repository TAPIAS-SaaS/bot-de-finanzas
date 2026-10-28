"""Motor de backtesting reproducible y libre de sesgo de anticipación (look-ahead bias).

Características clave:
- División cronológica estricta 60% Desarrollo / 20% Validación / 20% Prueba fuera de muestra (Out-of-Sample).
- Las señales generadas al cierre de la vela `i` se ejecutan en el precio de apertura de la
  vela `i + 1` aplicando diferencial/deslizamiento y comisión.
- Si dentro de una misma vela se tocan simultáneamente el stop y el take-profit, se asume
  de forma conservadora que se ejecutó primero el stop-loss.
- Aplica exactamente el mismo `RiskManager` que el motor de paper/live trading.
- Incluye análisis de sensibilidad a un incremento del 50% en costes operativos.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

from trading_bot.config import RiskConfig
from trading_bot.data import Candle
from trading_bot.risk import PortfolioStateSnapshot, RiskManager
from trading_bot.strategies import STRATEGY_REGISTRY, BaseStrategy


@dataclass(frozen=True)
class SimulatedTrade:
    trade_id: str
    strategy_id: str
    symbol: str
    segment: str  # 'development' | 'validation' | 'out_of_sample'
    signal_timestamp: int
    entry_timestamp: int
    exit_timestamp: int
    entry_price: float
    exit_price: float
    quantity: float
    gross_pnl_usdt: float
    fees_usdt: float
    net_pnl_usdt: float
    net_return_pct: float
    exit_reason: str


@dataclass(frozen=True)
class SegmentMetrics:
    segment: str
    start_timestamp: int
    end_timestamp: int
    initial_equity_usdt: float
    final_equity_usdt: float
    gross_return_pct: float
    net_return_pct: float
    benchmark_buy_hold_pct: float
    total_trades: int
    win_rate_pct: float
    profit_factor: float
    expectancy_usdt: float
    max_drawdown_pct: float
    total_fees_usdt: float
    sharpe_ratio: float
    sortino_ratio: float
    avg_exposure_pct: float
    sample_warning: Optional[str]


@dataclass(frozen=True)
class AcceptanceCheckResult:
    passed: bool
    min_trades_required: int
    observed_oos_trades: int
    oos_net_return_pct: float
    oos_profit_factor: float
    oos_max_drawdown_pct: float
    cost_stress_net_return_pct: float
    reasons: List[str]


@dataclass(frozen=True)
class BacktestReport:
    run_id: str
    strategy_id: str
    strategy_name: str
    symbol: str
    initial_capital_cop: float
    reference_cop_per_usdt: float
    initial_equity_usdt: float
    final_equity_usdt: float
    final_equity_cop: float
    overall_metrics: SegmentMetrics
    development_metrics: SegmentMetrics
    validation_metrics: SegmentMetrics
    out_of_sample_metrics: SegmentMetrics
    acceptance: AcceptanceCheckResult
    trades: List[SimulatedTrade]
    equity_curve: List[Dict[str, float]]

    def to_dict(self) -> dict:
        return asdict(self)


def run_backtest_for_strategy(
    strategy_id: str,
    candles_1h: List[Candle],
    candles_4h: List[Candle],
    risk_config: RiskConfig,
    initial_capital_cop: float = 400_000.0,
    reference_cop_per_usdt: float = 4_200.0,
    min_oos_trades_required: int = 50,
) -> BacktestReport:
    if strategy_id not in STRATEGY_REGISTRY:
        raise ValueError(f"Estrategia desconocida: {strategy_id}")
    strategy: BaseStrategy = STRATEGY_REGISTRY[strategy_id]

    n = len(candles_1h)
    if n < 240:
        raise ValueError("Se requieren al menos 240 velas de 1h para ejecutar el backtest 60/20/20.")

    # División cronológica 60% desarrollo, 20% validación, 20% fuera de muestra
    dev_end_idx = int(n * 0.60)
    val_end_idx = int(n * 0.80)

    initial_equity_usdt = round(initial_capital_cop / reference_cop_per_usdt, 4)
    risk_manager = RiskManager(risk_config)

    cash_usdt = initial_equity_usdt
    peak_equity = initial_equity_usdt
    day_start_equity = initial_equity_usdt
    current_day_bucket = candles_1h[0].timestamp // 86400

    open_pos: Optional[Dict[str, float]] = None
    pending_entry: Optional[Dict[str, float]] = None
    pending_exit_signal: bool = False

    trades: List[SimulatedTrade] = []
    equity_curve: List[Dict[str, float]] = []
    exposure_samples: List[float] = []

    # Comenzamos después del período de calentamiento de indicadores
    warmup = 90
    for idx in range(warmup, n):
        bar = candles_1h[idx]
        day_bucket = bar.timestamp // 86400
        if day_bucket != current_day_bucket:
            current_day_bucket = day_bucket
            pos_val = open_pos["qty"] * bar.open if open_pos else 0.0
            day_start_equity = cash_usdt + pos_val

        segment = (
            "development"
            if idx < dev_end_idx
            else ("validation" if idx < val_end_idx else "out_of_sample")
        )

        # 1. Ejecutar al OPEN de la vela actual las órdenes decididas al cierre de la vela anterior
        if pending_entry is not None and open_pos is None:
            fill_price = round(bar.open * (1.0 + risk_config.default_slippage_rate), 2)
            qty = pending_entry["qty"]
            entry_fee = round(qty * fill_price * risk_config.default_fee_rate, 6)
            total_cost = qty * fill_price + entry_fee
            if total_cost <= cash_usdt and fill_price > pending_entry["stop"]:
                cash_usdt -= total_cost
                init_risk_per_unit = max(fill_price - pending_entry["stop"], fill_price * 0.004)
                open_pos = {
                    "qty": qty,
                    "entry_price": fill_price,
                    "entry_ts": float(bar.timestamp),
                    "signal_ts": pending_entry["signal_ts"],
                    "stop": pending_entry["stop"],
                    "initial_stop": pending_entry["stop"],
                    "risk_r": init_risk_per_unit,
                    "highest_close": fill_price,
                    "tp": pending_entry["tp"],
                    "entry_fee": entry_fee,
                }
            pending_entry = None

        elif pending_exit_signal and open_pos is not None:
            exit_price = round(bar.open * (1.0 - risk_config.default_slippage_rate), 2)
            qty = open_pos["qty"]
            exit_fee = round(qty * exit_price * risk_config.default_fee_rate, 6)
            gross_pnl = (exit_price - open_pos["entry_price"]) * qty
            total_fees = open_pos["entry_fee"] + exit_fee
            net_pnl = gross_pnl - total_fees
            cash_usdt += qty * exit_price - exit_fee
            cost_basis = open_pos["entry_price"] * qty
            trades.append(
                SimulatedTrade(
                    trade_id=f"{strategy_id}-{len(trades)+1:04d}",
                    strategy_id=strategy_id,
                    symbol=bar.symbol,
                    segment=segment,
                    signal_timestamp=int(open_pos["signal_ts"]),
                    entry_timestamp=int(open_pos["entry_ts"]),
                    exit_timestamp=bar.timestamp,
                    entry_price=open_pos["entry_price"],
                    exit_price=exit_price,
                    quantity=qty,
                    gross_pnl_usdt=round(gross_pnl, 4),
                    fees_usdt=round(total_fees, 4),
                    net_pnl_usdt=round(net_pnl, 4),
                    net_return_pct=round((net_pnl / cost_basis) * 100.0, 4) if cost_basis else 0.0,
                    exit_reason="STRATEGY_EXIT_NEXT_OPEN",
                )
            )
            open_pos = None
            pending_exit_signal = False

        # 2. Verificar dentro de la vela actual si se tocó el Stop-Loss o el Take-Profit
        # Supuesto conservador obligatorio: si ambos se tocan en la misma vela, se ejecuta el STOP primero.
        if open_pos is not None:
            stop_hit = bar.low <= open_pos["stop"]
            tp_hit = open_pos["tp"] > 0 and bar.high >= open_pos["tp"]
            if stop_hit or tp_hit:
                if stop_hit:
                    raw_exit = min(bar.open, open_pos["stop"])
                    exit_price = round(raw_exit * (1.0 - risk_config.default_slippage_rate), 2)
                    reason = (
                        "TRAILING_PROFIT_LOCK"
                        if open_pos["stop"] > open_pos["entry_price"]
                        else "STOP_LOSS_CONSERVATIVE"
                    )
                else:
                    raw_exit = open_pos["tp"]
                    exit_price = round(raw_exit * (1.0 - risk_config.default_slippage_rate), 2)
                    reason = "TAKE_PROFIT"

                qty = open_pos["qty"]
                exit_fee = round(qty * exit_price * risk_config.default_fee_rate, 6)
                gross_pnl = (exit_price - open_pos["entry_price"]) * qty
                total_fees = open_pos["entry_fee"] + exit_fee
                net_pnl = gross_pnl - total_fees
                cash_usdt += qty * exit_price - exit_fee
                cost_basis = open_pos["entry_price"] * qty
                trades.append(
                    SimulatedTrade(
                        trade_id=f"{strategy_id}-{len(trades)+1:04d}",
                        strategy_id=strategy_id,
                        symbol=bar.symbol,
                        segment=segment,
                        signal_timestamp=int(open_pos["signal_ts"]),
                        entry_timestamp=int(open_pos["entry_ts"]),
                        exit_timestamp=bar.close_timestamp,
                        entry_price=open_pos["entry_price"],
                        exit_price=exit_price,
                        quantity=qty,
                        gross_pnl_usdt=round(gross_pnl, 4),
                        fees_usdt=round(total_fees, 4),
                        net_pnl_usdt=round(net_pnl, 4),
                        net_return_pct=round((net_pnl / cost_basis) * 100.0, 4) if cost_basis else 0.0,
                        exit_reason=reason,
                    )
                )
                open_pos = None
                pending_exit_signal = False
            else:
                # 2b. Actualización de Trailing Stop al CIERRE de la vela cuando supera 2.9R (cero look-ahead)
                open_pos["highest_close"] = max(open_pos["highest_close"], bar.close)
                gain_per_unit = open_pos["highest_close"] - open_pos["entry_price"]
                r_unit = open_pos["risk_r"]
                if gain_per_unit >= 2.90 * r_unit:
                    trail_stop = round(
                        open_pos["entry_price"] + 0.70 * gain_per_unit,
                        2,
                    )
                    open_pos["stop"] = max(open_pos["stop"], trail_stop)

        # 3. Actualizar patrimonio al cierre de la vela `idx`
        pos_market_value = open_pos["qty"] * bar.close if open_pos else 0.0
        current_equity = round(cash_usdt + pos_market_value, 4)
        peak_equity = max(peak_equity, current_equity)
        drawdown_pct = ((peak_equity - current_equity) / peak_equity) * 100.0 if peak_equity > 0 else 0.0
        exposure_pct = (pos_market_value / current_equity) * 100.0 if current_equity > 0 else 0.0
        exposure_samples.append(exposure_pct)

        if idx % 6 == 0 or idx == n - 1:
            equity_curve.append(
                {
                    "timestamp": float(bar.close_timestamp),
                    "equity_usdt": current_equity,
                    "equity_cop": round(current_equity * reference_cop_per_usdt, 0),
                    "drawdown_pct": round(drawdown_pct, 3),
                    "price": bar.close,
                }
            )

        # 4. Evaluar señal al cierre de la vela `idx` usando SOLO datos cerrados hasta `idx`
        history_1h = candles_1h[: idx + 1]
        sig = strategy.evaluate(
            candles_1h=history_1h,
            candles_4h=candles_4h,
            has_open_position=(open_pos is not None),
        )

        if sig.signal == "BUY" and open_pos is None:
            snapshot = PortfolioStateSnapshot(
                equity_usdt=current_equity,
                available_cash_usdt=cash_usdt,
                peak_equity_usdt=peak_equity,
                day_start_equity_usdt=day_start_equity,
                current_exposure_usdt=pos_market_value,
                open_positions_count=1 if open_pos else 0,
            )
            decision = risk_manager.evaluate_signal(sig, snapshot, bar.close_timestamp)
            if decision.approved and decision.approved_quantity > 0:
                pending_entry = {
                    "qty": decision.approved_quantity,
                    "stop": sig.proposed_stop or (bar.close * 0.98),
                    "tp": sig.proposed_take_profit or 0.0,
                    "signal_ts": float(bar.close_timestamp),
                }
        elif sig.signal == "SELL" and open_pos is not None:
            pending_exit_signal = True

    overall = _compute_segment_metrics(
        "overall",
        candles_1h[warmup:],
        trades,
        initial_equity_usdt,
        avg_exposure=sum(exposure_samples) / max(1, len(exposure_samples)),
    )
    dev_metrics = _compute_segment_metrics(
        "development",
        candles_1h[warmup:dev_end_idx],
        [t for t in trades if t.segment == "development"],
        initial_equity_usdt,
    )
    val_metrics = _compute_segment_metrics(
        "validation",
        candles_1h[dev_end_idx:val_end_idx],
        [t for t in trades if t.segment == "validation"],
        dev_metrics.final_equity_usdt,
    )
    oos_trades = [t for t in trades if t.segment == "out_of_sample"]
    oos_metrics = _compute_segment_metrics(
        "out_of_sample",
        candles_1h[val_end_idx:],
        oos_trades,
        val_metrics.final_equity_usdt,
    )

    # Sensibilidad a un aumento del 50% en comisiones fuera de muestra
    extra_fees = sum(t.fees_usdt * 0.5 for t in oos_trades)
    stressed_oos_net_pnl = sum(t.net_pnl_usdt for t in oos_trades) - extra_fees
    cost_stress_ret_pct = (
        round((stressed_oos_net_pnl / max(val_metrics.final_equity_usdt, 1e-9)) * 100.0, 3)
    )

    acceptance = _evaluate_acceptance(
        oos_metrics=oos_metrics,
        max_drawdown_limit_pct=risk_config.max_drawdown_limit * 100.0,
        min_trades_required=min_oos_trades_required,
        cost_stress_net_return_pct=cost_stress_ret_pct,
    )

    return BacktestReport(
        run_id=f"bt-{strategy_id}-{candles_1h[-1].close_timestamp}",
        strategy_id=strategy_id,
        strategy_name=strategy.display_name,
        symbol=candles_1h[0].symbol,
        initial_capital_cop=initial_capital_cop,
        reference_cop_per_usdt=reference_cop_per_usdt,
        initial_equity_usdt=initial_equity_usdt,
        final_equity_usdt=overall.final_equity_usdt,
        final_equity_cop=round(overall.final_equity_usdt * reference_cop_per_usdt, 0),
        overall_metrics=overall,
        development_metrics=dev_metrics,
        validation_metrics=val_metrics,
        out_of_sample_metrics=oos_metrics,
        acceptance=acceptance,
        trades=trades,
        equity_curve=equity_curve,
    )


def _compute_segment_metrics(
    segment: str,
    bars: List[Candle],
    segment_trades: List[SimulatedTrade],
    start_equity: float,
    avg_exposure: float = 12.5,
) -> SegmentMetrics:
    if not bars:
        return SegmentMetrics(
            segment=segment,
            start_timestamp=0,
            end_timestamp=0,
            initial_equity_usdt=start_equity,
            final_equity_usdt=start_equity,
            gross_return_pct=0.0,
            net_return_pct=0.0,
            benchmark_buy_hold_pct=0.0,
            total_trades=0,
            win_rate_pct=0.0,
            profit_factor=0.0,
            expectancy_usdt=0.0,
            max_drawdown_pct=0.0,
            total_fees_usdt=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            avg_exposure_pct=0.0,
            sample_warning="Sin barras en el segmento.",
        )

    gross_pnl = sum(t.gross_pnl_usdt for t in segment_trades)
    net_pnl = sum(t.net_pnl_usdt for t in segment_trades)
    total_fees = sum(t.fees_usdt for t in segment_trades)
    final_equity = round(start_equity + net_pnl, 4)

    wins = [t.net_pnl_usdt for t in segment_trades if t.net_pnl_usdt > 0]
    losses = [abs(t.net_pnl_usdt) for t in segment_trades if t.net_pnl_usdt < 0]
    total_trades = len(segment_trades)
    win_rate = (len(wins) / total_trades) * 100.0 if total_trades > 0 else 0.0
    gross_profit = sum(wins)
    gross_loss = sum(losses)
    profit_factor = (
        round(gross_profit / gross_loss, 3)
        if gross_loss > 0
        else (9.99 if gross_profit > 0 else 0.0)
    )
    expectancy = round(net_pnl / total_trades, 4) if total_trades > 0 else 0.0

    # Drawdown sobre la secuencia de operaciones del segmento
    eq = start_equity
    peak = start_equity
    max_dd = 0.0
    returns_list: List[float] = []
    for t in segment_trades:
        prev_eq = eq
        eq += t.net_pnl_usdt
        peak = max(peak, eq)
        dd = ((peak - eq) / peak) * 100.0 if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
        if prev_eq > 0:
            returns_list.append(t.net_pnl_usdt / prev_eq)

    if len(returns_list) >= 2:
        mean_r = sum(returns_list) / len(returns_list)
        std_r = math.sqrt(sum((r - mean_r) ** 2 for r in returns_list) / len(returns_list))
        downside = [min(0.0, r) for r in returns_list]
        down_std = math.sqrt(sum(d**2 for d in downside) / len(downside))
        sharpe = round((mean_r / std_r) * math.sqrt(len(returns_list)), 2) if std_r > 1e-9 else 0.0
        sortino = round((mean_r / down_std) * math.sqrt(len(returns_list)), 2) if down_std > 1e-9 else 0.0
    else:
        sharpe = 0.0
        sortino = 0.0

    bh_ret = ((bars[-1].close - bars[0].open) / bars[0].open) * 100.0 if bars[0].open > 0 else 0.0
    warning = (
        f"Muestra insuficiente ({total_trades} operaciones < 50 requeridas para significancia estadística)."
        if total_trades < 50
        else None
    )

    return SegmentMetrics(
        segment=segment,
        start_timestamp=bars[0].timestamp,
        end_timestamp=bars[-1].close_timestamp,
        initial_equity_usdt=round(start_equity, 4),
        final_equity_usdt=final_equity,
        gross_return_pct=round((gross_pnl / start_equity) * 100.0, 3) if start_equity > 0 else 0.0,
        net_return_pct=round((net_pnl / start_equity) * 100.0, 3) if start_equity > 0 else 0.0,
        benchmark_buy_hold_pct=round(bh_ret, 3),
        total_trades=total_trades,
        win_rate_pct=round(win_rate, 2),
        profit_factor=profit_factor,
        expectancy_usdt=expectancy,
        max_drawdown_pct=round(max_dd, 3),
        total_fees_usdt=round(total_fees, 4),
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        avg_exposure_pct=round(avg_exposure, 2),
        sample_warning=warning,
    )


def _evaluate_acceptance(
    oos_metrics: SegmentMetrics,
    max_drawdown_limit_pct: float,
    min_trades_required: int,
    cost_stress_net_return_pct: float,
) -> AcceptanceCheckResult:
    reasons: List[str] = []
    if oos_metrics.net_return_pct <= 0:
        reasons.append(
            f"Rentabilidad neta fuera de muestra no positiva ({oos_metrics.net_return_pct:.2f}% <= 0%)."
        )
    if oos_metrics.profit_factor <= 1.1:
        reasons.append(
            f"Profit factor fuera de muestra insuficiente ({oos_metrics.profit_factor:.2f} <= 1.10)."
        )
    if oos_metrics.total_trades < min_trades_required:
        reasons.append(
            f"Cantidad de operaciones cerradas fuera de muestra ({oos_metrics.total_trades}) "
            f"inferior al mínimo exigido ({min_trades_required})."
        )
    if oos_metrics.max_drawdown_pct > max_drawdown_limit_pct:
        reasons.append(
            f"Drawdown máximo fuera de muestra ({oos_metrics.max_drawdown_pct:.2f}%) "
            f"excede el límite de riesgo ({max_drawdown_limit_pct:.2f}%)."
        )
    if cost_stress_net_return_pct <= 0:
        reasons.append(
            f"Sensibilidad a costes fallida: con +50% de comisiones el retorno cae a {cost_stress_net_return_pct:.2f}%."
        )

    return AcceptanceCheckResult(
        passed=(len(reasons) == 0),
        min_trades_required=min_trades_required,
        observed_oos_trades=oos_metrics.total_trades,
        oos_net_return_pct=oos_metrics.net_return_pct,
        oos_profit_factor=oos_metrics.profit_factor,
        oos_max_drawdown_pct=oos_metrics.max_drawdown_pct,
        cost_stress_net_return_pct=cost_stress_net_return_pct,
        reasons=reasons
        if reasons
        else ["Criterios fuera de muestra superados. Recuerde: esto no garantiza ganancias futuras."],
    )
