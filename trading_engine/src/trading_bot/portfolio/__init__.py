"""Gestión contable de portafolio en USDT y COP para Paper Trading."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Optional


@dataclass
class VirtualPosition:
    symbol: str
    strategy_id: str
    quantity: float
    entry_price: float
    stop_price: float
    take_profit_price: Optional[float]
    opened_at: int
    entry_fee_usdt: float

    def unrealized_pnl_usdt(self, mark_price: float) -> float:
        return round((mark_price - self.entry_price) * self.quantity, 4)

    def to_dict(self, mark_price: float) -> dict:
        data = asdict(self)
        data["mark_price"] = mark_price
        data["unrealized_pnl_usdt"] = self.unrealized_pnl_usdt(mark_price)
        data["notional_usdt"] = round(self.quantity * mark_price, 4)
        return data


class PaperPortfolio:
    def __init__(
        self,
        initial_capital_cop: float = 400_000.0,
        reference_cop_per_usdt: float = 4_200.0,
    ) -> None:
        self.initial_capital_cop = initial_capital_cop
        self.reference_cop_per_usdt = reference_cop_per_usdt
        self.initial_equity_usdt = round(initial_capital_cop / reference_cop_per_usdt, 4)
        self.cash_usdt = self.initial_equity_usdt
        self.peak_equity_usdt = self.initial_equity_usdt
        self.day_start_equity_usdt = self.initial_equity_usdt
        self.realized_pnl_usdt = 0.0
        self.total_fees_usdt = 0.0
        self.closed_trades_count = 0
        self.positions: Dict[str, VirtualPosition] = {}

    def total_equity_usdt(self, mark_prices: Dict[str, float]) -> float:
        pos_val = sum(
            pos.quantity * mark_prices.get(sym, pos.entry_price)
            for sym, pos in self.positions.items()
        )
        eq = round(self.cash_usdt + pos_val, 4)
        self.peak_equity_usdt = max(self.peak_equity_usdt, eq)
        return eq

    def current_drawdown_pct(self, mark_prices: Dict[str, float]) -> float:
        eq = self.total_equity_usdt(mark_prices)
        if self.peak_equity_usdt <= 0:
            return 0.0
        return round(((self.peak_equity_usdt - eq) / self.peak_equity_usdt) * 100.0, 4)
