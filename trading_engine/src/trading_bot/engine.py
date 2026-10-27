"""Coordinador principal (`TradingBotEngine`) del motor cuantitativo Python."""

from __future__ import annotations

from typing import Any, Dict, List

from trading_bot.ai import GeminiAdvisor
from trading_bot.backtesting import run_backtest_for_strategy
from trading_bot.config import BotSettings, load_settings_from_env
from trading_bot.data import (
    generate_deterministic_market_series,
    load_market_candles_for_engine,
)
from trading_bot.exchanges import SpotExchangeAdapter
from trading_bot.execution import OrderExecutionEngine
from trading_bot.forecasting import (
    BaselineStatisticalForecastProvider,
    TimesFMForecastProvider,
)
from trading_bot.monitoring import build_health_report
from trading_bot.persistence import SQLiteAuditStore
from trading_bot.portfolio import PaperPortfolio, VirtualPosition
from trading_bot.risk import PortfolioStateSnapshot, RiskManager
from trading_bot.strategies import STRATEGY_REGISTRY


class TradingBotEngine:
    def __init__(self, settings: BotSettings | None = None) -> None:
        self.settings = settings or load_settings_from_env()
        self.settings.validate()
        self.risk_manager = RiskManager(self.settings.risk)
        self.portfolio = PaperPortfolio(
            initial_capital_cop=self.settings.general.initial_capital_cop,
            reference_cop_per_usdt=self.settings.general.reference_cop_per_usdt,
        )
        self.exchange_adapter = SpotExchangeAdapter(self.settings)
        self.execution_engine = OrderExecutionEngine(mode=self.settings.general.trading_mode)
        self.audit_store = SQLiteAuditStore(self.settings.general.sqlite_db_path)
        self.timesfm_provider = TimesFMForecastProvider(
            enabled=self.settings.timesfm.enabled,
            model_version=self.settings.timesfm.model_version,
        )
        self.baseline_forecast_provider = BaselineStatisticalForecastProvider()
        self.gemini_advisor = GeminiAdvisor(
            allowed_strategies=self.settings.strategy.allowed_strategies,
            model_id=self.settings.gemini.model_id,
            max_calls_per_hour=self.settings.gemini.max_calls_per_hour,
        )
        self.paper_running = True
        self._step_counter = 0

    def run_paper_evaluation_step(
        self,
        symbol: str = "BTC/USDT",
        data_provider: str | None = None,
    ) -> Dict[str, Any]:
        """Ejecuta un ciclo determinista de evaluación en modo Paper Trading."""
        self._step_counter += 1
        provider = data_provider or self.settings.data.provider
        candles_1h, candles_4h = load_market_candles_for_engine(
            symbol=symbol,
            provider=provider,
            num_1h_bars=900,
        )
        last_bar = candles_1h[-1]
        strategy = STRATEGY_REGISTRY[self.settings.strategy.active_strategy_id]
        has_open = symbol in self.portfolio.positions
        signal = strategy.evaluate(candles_1h, candles_4h, has_open_position=has_open)

        mark_prices = {symbol: last_bar.close}
        eq_usdt = self.portfolio.total_equity_usdt(mark_prices)
        pos_exposure = sum(
            p.quantity * mark_prices.get(s, p.entry_price)
            for s, p in self.portfolio.positions.items()
        )
        snapshot = PortfolioStateSnapshot(
            equity_usdt=eq_usdt,
            available_cash_usdt=self.portfolio.cash_usdt,
            peak_equity_usdt=self.portfolio.peak_equity_usdt,
            day_start_equity_usdt=self.portfolio.day_start_equity_usdt,
            current_exposure_usdt=pos_exposure,
            open_positions_count=len(self.portfolio.positions),
            has_unknown_orders=self.execution_engine.has_unknown_orders,
            exchange_connected=True,
            kill_switch_active=self.risk_manager.kill_switch_active,
        )

        risk_decision = self.risk_manager.evaluate_signal(
            signal=signal,
            portfolio=snapshot,
            current_time_utc=last_bar.close_timestamp,
        )

        signal_id = f"sig-{symbol.replace('/', '')}-{last_bar.close_timestamp}-{self._step_counter}"
        risk_id = f"risk-{symbol.replace('/', '')}-{last_bar.close_timestamp}-{self._step_counter}"
        order_dict: Dict[str, Any] | None = None

        if risk_decision.approved and signal.signal == "BUY" and self.paper_running:
            client_oid = f"coid-{signal_id}"
            order = self.execution_engine.submit_order(
                client_order_id=client_oid,
                symbol=symbol,
                side="BUY",
                quantity=risk_decision.approved_quantity,
                reference_price=signal.reference_price,
                fee_rate=self.settings.risk.default_fee_rate,
                slippage_rate=self.settings.risk.default_slippage_rate,
            )
            if order.status in ("FILLED", "PARTIALLY_FILLED") and order.filled_qty > 0:
                cost = order.filled_qty * order.avg_fill_price + order.fee_usdt
                self.portfolio.cash_usdt = round(self.portfolio.cash_usdt - cost, 4)
                self.portfolio.total_fees_usdt = round(
                    self.portfolio.total_fees_usdt + order.fee_usdt, 4
                )
                self.portfolio.positions[symbol] = VirtualPosition(
                    symbol=symbol,
                    strategy_id=signal.strategy_id,
                    quantity=order.filled_qty,
                    entry_price=order.avg_fill_price,
                    stop_price=signal.proposed_stop or round(order.avg_fill_price * 0.98, 2),
                    take_profit_price=signal.proposed_take_profit,
                    opened_at=last_bar.close_timestamp,
                    entry_fee_usdt=order.fee_usdt,
                )
            order_dict = {
                "order_id": order.order_id,
                "client_order_id": order.client_order_id,
                "mode": order.mode,
                "symbol": order.symbol,
                "side": order.side,
                "quantity": order.requested_qty,
                "filled_quantity": order.filled_qty,
                "price": order.avg_fill_price,
                "fee_usdt": order.fee_usdt,
                "status": order.status,
            }

        self.audit_store.record_decision_chain(
            signal_id=signal_id,
            risk_decision_id=risk_id,
            signal_data=signal.to_dict(),
            risk_data=risk_decision.to_dict(),
            order_data=order_dict,
        )

        return {
            "signal_id": signal_id,
            "risk_decision_id": risk_id,
            "data_source": last_bar.source,
            "last_candle_close_utc": last_bar.close_timestamp,
            "signal": signal.to_dict(),
            "risk_decision": risk_decision.to_dict(),
            "order": order_dict,
        }

    def run_comparative_backtest(
        self,
        symbol: str = "BTC/USDT",
        data_provider: str | None = None,
    ) -> List[Dict[str, Any]]:
        provider = data_provider or self.settings.data.provider
        candles_1h, candles_4h = load_market_candles_for_engine(
            symbol=symbol,
            provider=provider,
            num_1h_bars=1000 if provider == "binance_public" else 1200,
        )
        reports: List[Dict[str, Any]] = []
        for strat_id in self.settings.strategy.allowed_strategies:
            rep = run_backtest_for_strategy(
                strategy_id=strat_id,
                candles_1h=candles_1h,
                candles_4h=candles_4h,
                risk_config=self.settings.risk,
                initial_capital_cop=self.settings.general.initial_capital_cop,
                reference_cop_per_usdt=self.settings.general.reference_cop_per_usdt,
                min_oos_trades_required=50,
            )
            reports.append(rep.to_dict())
        return reports

    def get_status_summary(self) -> Dict[str, Any]:
        candles_1h, _ = generate_deterministic_market_series("BTC/USDT", num_1h_bars=64)
        last_ts = candles_1h[-1].close_timestamp
        health = build_health_report(
            trading_mode=self.settings.general.trading_mode,
            kill_switch_active=self.risk_manager.kill_switch_active,
            last_data_timestamp=last_ts,
            max_staleness_seconds=self.settings.risk.max_data_staleness_seconds,
            now_utc=last_ts + 60,
        )
        live_gate = self.exchange_adapter.verify_live_readiness(
            risk_manager_available=True,
            state_reconciled=not self.execution_engine.has_unknown_orders,
            audit_store_healthy=True,
        )
        return {
            "health": health.to_dict(),
            "settings": self.settings.to_public_dict(),
            "live_readiness": live_gate.to_dict(),
            "paper_running": self.paper_running,
        }
