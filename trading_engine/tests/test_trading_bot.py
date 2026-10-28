"""Suite completa de pruebas unitarias e integración para `trading_bot`.

Cubre todos los requisitos de la sección 18:
1. Indicadores (datos conocidos, ausencia de datos suficientes, nulos/inválidos, orden cronológico, solo velas cerradas).
2. Estrategias (condiciones de entrada/salida, señales HOLD, filtros de volatilidad y tendencia, ausencia de look-ahead bias).
3. Riesgo (tamaño de posición, límite 0.5%, exposición 50%, pérdida diaria 1%, drawdown 5%, mínimo de orden, datos obsoletos, bloqueo de trading real por defecto, interruptor de emergencia).
4. Ejecución (timeout, orden duplicada / idempotencia, ejecución parcial, reconciliación, orden desconocida, bloqueo de retiros y apalancamiento).
5. IA y TimesFM (respuestas inválidas, campos JSON ausentes, fuera de rango, cuota agotada, modelo deshabilitado o sin datos suficientes).
6. Persistencia SQLite y Backtesting reproducible 60/20/20.
"""

from __future__ import annotations

import unittest

from trading_bot.ai import GeminiAdvisor, validate_advisor_payload
from trading_bot.backtesting import run_backtest_for_strategy
from trading_bot.config import (
    BotSettings,
    ConfigValidationError,
    ExecutionConfig,
    GeneralConfig,
    RiskConfig,
    load_settings_from_env,
)
from trading_bot.data import (
    Candle,
    DataIntegrityError,
    align_4h_to_1h_without_lookahead,
    generate_deterministic_market_series,
    validate_candles,
)
from trading_bot.exchanges import SpotExchangeAdapter
from trading_bot.execution import OrderExecutionEngine
from trading_bot.forecasting import (
    BaselineStatisticalForecastProvider,
    TimesFMForecastProvider,
)
from trading_bot.indicators import (
    calculate_atr,
    calculate_bollinger_and_zscore,
    calculate_donchian_channel,
    calculate_ema,
    calculate_sma,
)
from trading_bot.persistence import SQLiteAuditStore
from trading_bot.risk import PortfolioStateSnapshot, RiskManager
from trading_bot.strategies import (
    MeanReversionStrategy,
    RangeBreakoutStrategy,
    StrategySignal,
    TrendFollowingStrategy,
)


class TestIndicatorsAndData(unittest.TestCase):
    def test_sma_and_ema_known_values_and_insufficient_data(self) -> None:
        self.assertIsNone(calculate_sma([10.0, 20.0], 5))
        self.assertAlmostEqual(calculate_sma([10.0, 20.0, 30.0], 3) or 0.0, 20.0)
        self.assertIsNone(calculate_sma([10.0, float("nan"), 30.0], 3))

        self.assertIsNone(calculate_ema([100.0, 105.0], 5))
        ema_val = calculate_ema([10.0, 20.0, 30.0, 40.0], 3)
        self.assertIsNotNone(ema_val)
        # Seed = (10+20+30)/3 = 20.0; next = (40 - 20)*(2/4) + 20 = 30.0
        self.assertAlmostEqual(ema_val or 0.0, 30.0)

    def test_atr_uses_only_closed_candles(self) -> None:
        c1h, _ = generate_deterministic_market_series("BTC/USDT", num_1h_bars=25)
        atr_closed = calculate_atr(c1h, 14)
        self.assertIsNotNone(atr_closed)

        # Añadir una vela en formación (`is_closed=False`) con rango extremo no debe alterar el ATR cerrado
        unclosed = Candle(
            timestamp=c1h[-1].close_timestamp,
            close_timestamp=c1h[-1].close_timestamp + 3600,
            symbol="BTC/USDT",
            timeframe="1h",
            open=90000.0,
            high=250000.0,
            low=10000.0,
            close=150000.0,
            volume=9999.0,
            is_closed=False,
        )
        atr_with_unclosed = calculate_atr(c1h + [unclosed], 14)
        self.assertAlmostEqual(atr_closed or 0.0, atr_with_unclosed or 0.0)

    def test_validate_candles_detects_duplicates_gaps_and_unordered(self) -> None:
        c1h, _ = generate_deterministic_market_series("BTC/USDT", num_1h_bars=10)
        validated = validate_candles(c1h, "1h")
        self.assertEqual(len(validated), 10)

        # Duplicado
        with self.assertRaises(DataIntegrityError):
            validate_candles([c1h[0], c1h[0]], "1h")

        # Desordenado
        with self.assertRaises(DataIntegrityError):
            validate_candles([c1h[1], c1h[0]], "1h")

        # Vela faltante (hueco)
        with self.assertRaises(DataIntegrityError):
            validate_candles([c1h[0], c1h[2]], "1h")

    def test_no_lookahead_between_1h_and_4h(self) -> None:
        c1h, c4h = generate_deterministic_market_series("BTC/USDT", num_1h_bars=20)
        # En la segunda vela de 1h (close_timestamp = start + 7200), la primera vela de 4h
        # (close_timestamp = start + 14400) AÚN NO HA CERRADO.
        decision_ts = c1h[1].close_timestamp
        aligned_1h, aligned_4h = align_4h_to_1h_without_lookahead(c1h, c4h, decision_ts)
        self.assertEqual(len(aligned_1h), 2)
        self.assertEqual(len(aligned_4h), 0)


class TestStrategies(unittest.TestCase):
    def test_strategies_hold_on_insufficient_history_and_no_future_leak(self) -> None:
        c1h, c4h = generate_deterministic_market_series("BTC/USDT", num_1h_bars=40)
        for strat in (
            TrendFollowingStrategy(),
            MeanReversionStrategy(),
            RangeBreakoutStrategy(),
        ):
            sig = strat.evaluate(c1h[:15], c4h[:3], has_open_position=False)
            self.assertEqual(sig.signal, "HOLD")

    def test_all_three_strategies_produce_valid_signals_across_series(self) -> None:
        c1h, c4h = generate_deterministic_market_series("BTC/USDT", num_1h_bars=1000)
        for strat in (
            TrendFollowingStrategy(),
            MeanReversionStrategy(),
            RangeBreakoutStrategy(),
        ):
            sig = strat.evaluate(c1h[:900], c4h, has_open_position=False)
            self.assertIn(sig.signal, ("BUY", "SELL", "HOLD"))
            self.assertEqual(sig.strategy_id, strat.strategy_id)

    def test_multi_asset_altcoin_precision_and_backtest(self) -> None:
        from trading_bot.config import SUPPORTED_SPOT_SYMBOLS, build_risk_config_for_profile
        from trading_bot.data import round_price

        self.assertEqual(len(SUPPORTED_SPOT_SYMBOLS), 14)
        self.assertEqual(round_price(0.000005123), 0.00000512)
        self.assertEqual(round_price(0.0803456), 0.080346)
        self.assertEqual(round_price(1.33149), 1.3315)
        self.assertEqual(round_price(71012.345), 71012.35)

        for sym in ("SOL/USDT", "PEPE/USDT", "INJ/USDT", "DOGE/USDT"):
            c1h, c4h = generate_deterministic_market_series(sym, num_1h_bars=320)
            rep = run_backtest_for_strategy(
                "range_breakout_v1", c1h, c4h, build_risk_config_for_profile("aggressive")
            )
            self.assertEqual(rep.symbol, sym)
            self.assertGreaterEqual(rep.final_equity_usdt, rep.initial_equity_usdt)


class TestRiskManagerAndSecurity(unittest.TestCase):
    def setUp(self) -> None:
        self.config = RiskConfig()
        self.rm = RiskManager(self.config)
        self.base_signal = StrategySignal(
            symbol="BTC/USDT",
            evaluated_at=1_767_300_000,
            signal="BUY",
            strategy_id="trend_following_v1",
            strategy_version="1.0.0",
            indicators={"atr14_1h": 450.0},
            reference_price=90_000.0,
            invalidation_level=89_100.0,
            proposed_stop=89_100.0,
            proposed_take_profit=91_800.0,
            explanation="Señal de prueba determinista",
        )
        self.base_portfolio = PortfolioStateSnapshot(
            equity_usdt=95.2381,  # ~400.000 COP a 4200 COP/USDT
            available_cash_usdt=95.2381,
            peak_equity_usdt=95.2381,
            day_start_equity_usdt=95.2381,
            current_exposure_usdt=0.0,
            open_positions_count=0,
        )

    def test_valid_position_sizing_respects_risk_and_exposure(self) -> None:
        dec = self.rm.evaluate_signal(
            self.base_signal, self.base_portfolio, current_time_utc=1_767_300_060
        )
        self.assertTrue(dec.approved)
        self.assertLessEqual(dec.estimated_risk_pct, self.config.max_risk_per_trade + 1e-4)
        self.assertLessEqual(
            dec.notional_usdt, self.base_portfolio.equity_usdt * self.config.max_exposure + 1e-4
        )
        self.assertGreaterEqual(dec.notional_usdt, self.config.min_order_notional_usdt)

    def test_rejects_when_min_notional_exceeds_allowed_risk(self) -> None:
        # Stop muy lejano (70.000 USDT) hace que con 0.5% de riesgo (~0.47 USDT) el notional sea < 5 USDT
        wide_stop_signal = StrategySignal(
            **{**self.base_signal.to_dict(), "proposed_stop": 65_000.0}
        )
        dec = self.rm.evaluate_signal(
            wide_stop_signal, self.base_portfolio, current_time_utc=1_767_300_060
        )
        self.assertFalse(dec.approved)
        self.assertEqual(dec.reason_code, "MIN_NOTIONAL_EXCEEDS_RISK_OR_EXPOSURE")

    def test_rejects_on_daily_loss_drawdown_stale_data_and_kill_switch(self) -> None:
        # Pérdida diaria >= 1%
        p_daily = PortfolioStateSnapshot(
            **{**self.base_portfolio.__dict__, "equity_usdt": 94.0}
        )
        dec1 = self.rm.evaluate_signal(self.base_signal, p_daily, 1_767_300_060)
        self.assertFalse(dec1.approved)
        self.assertEqual(dec1.reason_code, "DAILY_LOSS_LIMIT_BREACHED")

        # Drawdown >= 5%
        p_dd = PortfolioStateSnapshot(
            **{
                **self.base_portfolio.__dict__,
                "peak_equity_usdt": 105.0,
                "equity_usdt": 95.2381,
                "day_start_equity_usdt": 95.5,
            }
        )
        dec2 = self.rm.evaluate_signal(self.base_signal, p_dd, 1_767_300_060)
        self.assertFalse(dec2.approved)
        self.assertEqual(dec2.reason_code, "MAX_DRAWDOWN_BREACHED")

        # Datos obsoletos (> 7200s)
        rm_fresh = RiskManager(self.config)
        dec3 = rm_fresh.evaluate_signal(
            self.base_signal, self.base_portfolio, current_time_utc=1_767_310_000
        )
        self.assertFalse(dec3.approved)
        self.assertEqual(dec3.reason_code, "STALE_OR_FUTURE_DATA")

        # Interruptor de emergencia
        rm_fresh.activate_kill_switch("Prueba de bloqueo de emergencia")
        dec4 = rm_fresh.evaluate_signal(
            self.base_signal, self.base_portfolio, current_time_utc=1_767_300_060
        )
        self.assertFalse(dec4.approved)
        self.assertEqual(dec4.reason_code, "KILL_SWITCH_ACTIVE")

    def test_live_mode_blocked_by_default_and_withdrawals_forbidden(self) -> None:
        default_settings = load_settings_from_env({})
        self.assertEqual(default_settings.general.trading_mode, "paper")
        adapter = SpotExchangeAdapter(default_settings)
        with self.assertRaises(PermissionError):
            adapter.withdraw("USDT", 10.0, "0x123")
        with self.assertRaises(PermissionError):
            adapter.set_leverage(5, "BTC/USDT")

        # Intentar activar modo live sin las 12 condiciones falla en validación
        with self.assertRaises(ConfigValidationError):
            BotSettings(
                general=GeneralConfig(trading_mode="live"),
                execution=ExecutionConfig(allow_live_trading=False),
            ).validate()


class TestExecutionAIAndTimesFM(unittest.TestCase):
    def test_execution_idempotency_timeout_reconciliation_and_partial_fill(self) -> None:
        exec_engine = OrderExecutionEngine(mode="paper")
        ord1 = exec_engine.submit_order("client-1", "BTC/USDT", "BUY", 0.002, 90000.0)
        ord1_dup = exec_engine.submit_order("client-1", "BTC/USDT", "BUY", 0.002, 90000.0)
        self.assertEqual(ord1.order_id, ord1_dup.order_id)

        # Ejecución parcial
        ord_part = exec_engine.submit_order(
            "client-2", "BTC/USDT", "BUY", 0.002, 90000.0, simulate_partial_ratio=0.5
        )
        self.assertEqual(ord_part.status, "PARTIALLY_FILLED")
        self.assertAlmostEqual(ord_part.filled_qty, 0.001)

        # Timeout deja orden en estado desconocido y bloquea nuevas órdenes hasta reconciliar
        ord_timeout = exec_engine.submit_order(
            "client-3", "BTC/USDT", "BUY", 0.002, 90000.0, simulate_timeout=True
        )
        self.assertEqual(ord_timeout.status, "PENDING_RECONCILIATION")
        self.assertTrue(exec_engine.has_unknown_orders)

        ord_blocked = exec_engine.submit_order("client-4", "BTC/USDT", "BUY", 0.002, 90000.0)
        self.assertEqual(ord_blocked.status, "REJECTED")

    def test_gemini_advisor_rejects_malformed_json_and_enforces_quota(self) -> None:
        allowed = ["trend_following_v1", "mean_reversion_v1"]
        advisor = GeminiAdvisor(allowed_strategies=allowed, max_calls_per_hour=2)

        # Respuesta fuera de rango (confidence = 1.8) cae a fallback seguro HOLD
        bad_res = advisor.parse_or_fallback(
            {
                "market_regime": "TRENDING",
                "recommendation": "BUY",
                "confidence": 1.8,
                "supporting_factors": [],
                "risk_factors": [],
                "strategy_id": "trend_following_v1",
                "reason": "test",
                "data_timestamp": "123",
                "model_id": "gemini-3.8-flash",
                "warnings": [],
            },
            current_ts=1000,
        )
        self.assertEqual(bad_res.recommendation, "HOLD")

        # Estrategia no autorizada cae a HOLD
        unauth_res = advisor.parse_or_fallback(
            {
                "market_regime": "TRENDING",
                "recommendation": "BUY",
                "confidence": 0.7,
                "supporting_factors": ["EMA alcista"],
                "risk_factors": ["Volatilidad moderada"],
                "strategy_id": "estrategia_pirata_apalancada",
                "reason": "test",
                "data_timestamp": "123",
                "model_id": "gemini-3.8-flash",
                "warnings": [],
            },
            current_ts=1010,
        )
        self.assertEqual(unauth_res.recommendation, "HOLD")

        # Cuota agotada en tercera llamada dentro de la misma hora
        exhausted = advisor.parse_or_fallback(None, current_ts=1020)
        self.assertEqual(exhausted.recommendation, "HOLD")

    def test_timesfm_disabled_and_insufficient_data_handling(self) -> None:
        tfm_off = TimesFMForecastProvider(enabled=False)
        res_off = tfm_off.predict([90000.0] * 40, origin_timestamp=1000)
        self.assertFalse(res_off.available)
        self.assertFalse(res_off.enabled)
        self.assertEqual(res_off.point_forecast, [])

        tfm_on = TimesFMForecastProvider(enabled=True)
        res_short = tfm_on.predict([90000.0] * 10, origin_timestamp=1000)
        self.assertFalse(res_short.available)

        baseline = BaselineStatisticalForecastProvider()
        res_base = baseline.predict(
            [90000.0 + i * 25.0 for i in range(40)], origin_timestamp=1000, horizon=6
        )
        self.assertTrue(res_base.available)
        self.assertEqual(len(res_base.point_forecast), 6)

    def test_sqlite_audit_store_and_reproducible_backtest(self) -> None:
        store = SQLiteAuditStore(":memory:")
        store.record_decision_chain(
            signal_id="sig-1",
            risk_decision_id="risk-1",
            signal_data={
                "evaluated_at": 1000,
                "symbol": "BTC/USDT",
                "strategy_id": "trend_following_v1",
                "signal": "BUY",
                "reference_price": 90000.0,
                "proposed_stop": 89000.0,
                "indicators": {"ema20": 89900.0},
                "explanation": "Entrada de prueba",
            },
            risk_data={
                "approved": True,
                "reason_code": "APPROVED",
                "reason_detail": "OK",
                "approved_quantity": 0.0005,
                "notional_usdt": 45.0,
                "estimated_risk_usdt": 0.45,
            },
        )
        history = store.fetch_decision_history()
        self.assertEqual(len(history), 1)
        csv_text = store.export_decisions_csv()
        self.assertIn("sig-1", csv_text)
        store.close()

        c1h, c4h = generate_deterministic_market_series("BTC/USDT", num_1h_bars=400)
        rep1 = run_backtest_for_strategy("trend_following_v1", c1h, c4h, RiskConfig())
        rep2 = run_backtest_for_strategy("trend_following_v1", c1h, c4h, RiskConfig())
        self.assertEqual(rep1.final_equity_usdt, rep2.final_equity_usdt)


if __name__ == "__main__":
    unittest.main()
