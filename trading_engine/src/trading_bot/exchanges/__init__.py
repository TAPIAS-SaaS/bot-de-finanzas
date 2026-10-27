"""Adaptador de Exchange con restricciones estrictas de seguridad.

Reglas inquebrantables:
- Nunca habilita retiros (`withdraw` lanza `PermissionError` incondicionalmente).
- Solo permite mercado `spot` (sin margen, préstamos ni futuros).
- Valida las 12 condiciones antes de permitir el modo `live`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List

from trading_bot.config import LIVE_CONFIRMATION_PHRASE, BotSettings


@dataclass(frozen=True)
class ExchangeMarketLimits:
    symbol: str
    min_notional_usdt: float
    min_qty: float
    price_precision: int
    qty_precision: int
    maker_fee: float
    taker_fee: float


@dataclass(frozen=True)
class LiveReadinessCheck:
    ready_for_live: bool
    checks: Dict[str, bool]
    blocking_reasons: List[str]

    def to_dict(self) -> dict:
        return asdict(self)


class SpotExchangeAdapter:
    """Adaptador seguro para exchanges Spot (compatible con CCXT cuando está instalado)."""

    MARKET_LIMITS: Dict[str, ExchangeMarketLimits] = {
        "BTC/USDT": ExchangeMarketLimits(
            symbol="BTC/USDT",
            min_notional_usdt=5.0,
            min_qty=0.00001,
            price_precision=2,
            qty_precision=5,
            maker_fee=0.001,
            taker_fee=0.001,
        ),
        "ETH/USDT": ExchangeMarketLimits(
            symbol="ETH/USDT",
            min_notional_usdt=5.0,
            min_qty=0.0001,
            price_precision=2,
            qty_precision=4,
            maker_fee=0.001,
            taker_fee=0.001,
        ),
    }

    def __init__(self, settings: BotSettings) -> None:
        self.settings = settings

    def withdraw(self, *args: object, **kwargs: object) -> None:
        raise PermissionError(
            "OPERACIÓN PROHIBIDA: Los retiros de fondos mediante API están deshabilitados por diseño."
        )

    def set_leverage(self, *args: object, **kwargs: object) -> None:
        raise PermissionError(
            "OPERACIÓN PROHIBIDA: El apalancamiento y el margen están deshabilitados en v1."
        )

    def get_market_limits(self, symbol: str) -> ExchangeMarketLimits:
        if symbol not in self.MARKET_LIMITS:
            raise ValueError(f"Símbolo spot no habilitado: {symbol}")
        return self.MARKET_LIMITS[symbol]

    def verify_live_readiness(
        self,
        risk_manager_available: bool = True,
        state_reconciled: bool = True,
        audit_store_healthy: bool = True,
    ) -> LiveReadinessCheck:
        checks = {
            "trading_mode_is_live": self.settings.general.trading_mode == "live",
            "allow_live_trading_flag": self.settings.execution.allow_live_trading,
            "explicit_risk_confirmation": (
                self.settings.execution.live_trading_confirmation == LIVE_CONFIRMATION_PHRASE
            ),
            "mandatory_tests_passed": self.settings.execution.mandatory_tests_passed,
            "out_of_sample_approved": self.settings.execution.out_of_sample_approved,
            "valid_api_credentials": self.settings.exchange.has_api_credentials,
            "account_eligibility_verified": self.settings.exchange.account_eligibility_verified,
            "spot_market_only": (
                self.settings.exchange.market_type == "spot"
                and not self.settings.risk.allow_leverage
                and not self.settings.risk.allow_margin
                and not self.settings.risk.allow_short
            ),
            "withdrawals_disabled": not self.settings.risk.allow_withdrawals,
            "risk_manager_available": risk_manager_available,
            "balance_and_orders_reconciled": state_reconciled,
            "audit_log_operational": audit_store_healthy,
        }
        reasons = [
            f"Control fallido: {key}" for key, passed in checks.items() if not passed
        ]
        return LiveReadinessCheck(
            ready_for_live=(len(reasons) == 0),
            checks=checks,
            blocking_reasons=reasons,
        )
