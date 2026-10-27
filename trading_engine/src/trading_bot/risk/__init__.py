"""Gestor de riesgo determinista e independiente (`RiskManager`).

Ninguna salida de Gemini, TimesFM o una estrategia puede elevar ni anular
estos límites de seguridad.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import List, Optional

from trading_bot.config import RiskConfig
from trading_bot.strategies import StrategySignal


@dataclass(frozen=True)
class PortfolioStateSnapshot:
    equity_usdt: float
    available_cash_usdt: float
    peak_equity_usdt: float
    day_start_equity_usdt: float
    current_exposure_usdt: float
    open_positions_count: int
    has_unknown_orders: bool = False
    exchange_connected: bool = True
    kill_switch_active: bool = False


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason_code: str
    reason_detail: str
    approved_quantity: float
    notional_usdt: float
    estimated_risk_usdt: float
    estimated_risk_pct: float
    estimated_fees_usdt: float
    stop_price: Optional[float]

    def to_dict(self) -> dict:
        return asdict(self)


class RiskManager:
    """Evalúa cada señal de forma determinista antes de permitir una orden."""

    def __init__(self, config: RiskConfig) -> None:
        self.config = config
        self._kill_switch_active = False
        self._kill_switch_reason = ""
        self._drawdown_lock_active = False

    @property
    def kill_switch_active(self) -> bool:
        return self._kill_switch_active

    @property
    def kill_switch_reason(self) -> str:
        return self._kill_switch_reason

    def activate_kill_switch(self, reason: str) -> None:
        self._kill_switch_active = True
        self._kill_switch_reason = reason.strip() or "Activación manual de emergencia"

    def reset_kill_switch(self, explicit_authorization: bool = False) -> None:
        if not explicit_authorization:
            raise PermissionError(
                "Se requiere autorización explícita para desactivar el interruptor de emergencia."
            )
        self._kill_switch_active = False
        self._kill_switch_reason = ""
        self._drawdown_lock_active = False

    def evaluate_signal(
        self,
        signal: StrategySignal,
        portfolio: PortfolioStateSnapshot,
        current_time_utc: int,
    ) -> RiskDecision:
        # Las señales SELL para cerrar una posición existente se permiten incluso en bloqueo de nuevas entradas
        if signal.signal == "SELL":
            return RiskDecision(
                approved=True,
                reason_code="APPROVED_EXIT",
                reason_detail="Orden de salida protectora autorizada.",
                approved_quantity=0.0,
                notional_usdt=0.0,
                estimated_risk_usdt=0.0,
                estimated_risk_pct=0.0,
                estimated_fees_usdt=0.0,
                stop_price=None,
            )

        if signal.signal != "BUY":
            return self._reject("HOLD_SIGNAL", "La estrategia no solicita entrada (HOLD).")

        if self._kill_switch_active or portfolio.kill_switch_active:
            return self._reject(
                "KILL_SWITCH_ACTIVE",
                f"Interruptor de emergencia activo: {self._kill_switch_reason or 'bloqueo operativo'}.",
            )

        if not portfolio.exchange_connected:
            return self._reject(
                "EXCHANGE_DISCONNECTED",
                "Conexión con el proveedor de datos/exchange no disponible.",
            )

        if portfolio.has_unknown_orders:
            return self._reject(
                "UNKNOWN_ORDER_STATE",
                "Existen órdenes pendientes o en estado desconocido sin reconciliar.",
            )

        staleness = current_time_utc - signal.evaluated_at
        if staleness > self.config.max_data_staleness_seconds or staleness < 0:
            return self._reject(
                "STALE_OR_FUTURE_DATA",
                f"Datos obsoletos o desincronizados (desfase={staleness}s).",
            )

        if portfolio.equity_usdt <= 0 or portfolio.available_cash_usdt <= 0:
            return self._reject("INSUFFICIENT_EQUITY", "Saldo disponible insuficiente.")

        # Comprobación de drawdown acumulado desde el máximo
        peak = max(portfolio.peak_equity_usdt, portfolio.equity_usdt)
        current_drawdown = (peak - portfolio.equity_usdt) / peak if peak > 0 else 0.0
        if current_drawdown >= self.config.max_drawdown_limit or self._drawdown_lock_active:
            self._drawdown_lock_active = True
            return self._reject(
                "MAX_DRAWDOWN_BREACHED",
                f"Drawdown acumulado ({current_drawdown*100:.2f}%) alcanza o supera el límite ({self.config.max_drawdown_limit*100:.2f}%).",
            )

        # Comprobación de pérdida diaria
        day_ref = max(portfolio.day_start_equity_usdt, 1e-9)
        daily_loss = (day_ref - portfolio.equity_usdt) / day_ref
        if daily_loss >= self.config.daily_loss_limit:
            return self._reject(
                "DAILY_LOSS_LIMIT_BREACHED",
                f"Pérdida diaria ({daily_loss*100:.2f}%) alcanza o supera el límite ({self.config.daily_loss_limit*100:.2f}%).",
            )

        if portfolio.open_positions_count >= self.config.max_concurrent_positions:
            return self._reject(
                "MAX_POSITIONS_REACHED",
                f"Número máximo de posiciones simultáneas alcanzado ({self.config.max_concurrent_positions}).",
            )

        if signal.proposed_stop is None or signal.proposed_stop <= 0:
            return self._reject("MISSING_STOP_LOSS", "La señal no incluye un nivel de stop válido.")

        entry_price = signal.reference_price * (1.0 + self.config.default_slippage_rate)
        if signal.proposed_stop >= entry_price:
            return self._reject(
                "INVALID_STOP_DISTANCE",
                f"El stop propuesto ({signal.proposed_stop}) debe ser inferior al precio de entrada estimado ({entry_price:.2f}).",
            )

        # Cálculo de tamaño de posición considerando distancia al stop, comisiones y deslizamiento
        stop_exit_price = signal.proposed_stop * (1.0 - self.config.default_slippage_rate)
        price_loss_per_unit = entry_price - stop_exit_price
        fee_per_unit = (entry_price + stop_exit_price) * self.config.default_fee_rate
        total_loss_per_unit = price_loss_per_unit + fee_per_unit

        max_risk_usdt = portfolio.equity_usdt * self.config.max_risk_per_trade
        raw_qty_by_risk = max_risk_usdt / total_loss_per_unit

        # Límite por exposición bruta máxima (50% del patrimonio) y efectivo disponible
        remaining_exposure_usdt = max(
            0.0,
            portfolio.equity_usdt * self.config.max_exposure - portfolio.current_exposure_usdt,
        )
        max_notional_allowed = min(
            remaining_exposure_usdt,
            portfolio.available_cash_usdt / (1.0 + self.config.default_fee_rate),
        )
        max_qty_by_exposure = max_notional_allowed / entry_price if entry_price > 0 else 0.0

        final_qty = round(min(raw_qty_by_risk, max_qty_by_exposure), 6)
        notional_usdt = final_qty * entry_price
        estimated_fees_usdt = final_qty * fee_per_unit
        estimated_risk_usdt = final_qty * total_loss_per_unit
        estimated_risk_pct = estimated_risk_usdt / portfolio.equity_usdt

        if notional_usdt < self.config.min_order_notional_usdt:
            # Regla fundamental: si la posición mínima necesaria no respeta los límites de riesgo, rechazar
            return self._reject(
                "MIN_NOTIONAL_EXCEEDS_RISK_OR_EXPOSURE",
                (
                    f"El valor de la orden ({notional_usdt:.2f} USDT) es inferior al mínimo del exchange "
                    f"({self.config.min_order_notional_usdt:.2f} USDT) sin exceder el riesgo de "
                    f"{self.config.max_risk_per_trade*100:.2f}% ({max_risk_usdt:.2f} USDT)."
                ),
            )

        return RiskDecision(
            approved=True,
            reason_code="APPROVED",
            reason_detail=(
                f"Posición aprobada: {final_qty:.6f} unidades ({notional_usdt:.2f} USDT), "
                f"riesgo estimado {estimated_risk_usdt:.2f} USDT ({estimated_risk_pct*100:.2f}% del patrimonio)."
            ),
            approved_quantity=final_qty,
            notional_usdt=round(notional_usdt, 4),
            estimated_risk_usdt=round(estimated_risk_usdt, 4),
            estimated_risk_pct=round(estimated_risk_pct, 6),
            estimated_fees_usdt=round(estimated_fees_usdt, 4),
            stop_price=signal.proposed_stop,
        )

    def _reject(self, code: str, detail: str) -> RiskDecision:
        return RiskDecision(
            approved=False,
            reason_code=code,
            reason_detail=detail,
            approved_quantity=0.0,
            notional_usdt=0.0,
            estimated_risk_usdt=0.0,
            estimated_risk_pct=0.0,
            estimated_fees_usdt=0.0,
            stop_price=None,
        )
