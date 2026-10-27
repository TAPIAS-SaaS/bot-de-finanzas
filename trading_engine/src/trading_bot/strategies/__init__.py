"""Sistema de tres estrategias independientes con interfaz común tipada.

La señal devuelta NO constituye una autorización para enviar una orden.
Toda orden pasa obligatoriamente por el `RiskManager`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

from trading_bot.data import Candle, align_4h_to_1h_without_lookahead
from trading_bot.indicators import (
    calculate_atr,
    calculate_bollinger_and_zscore,
    calculate_donchian_channel,
    calculate_ema,
    calculate_relative_volume,
)


@dataclass(frozen=True)
class StrategySignal:
    symbol: str
    evaluated_at: int  # UTC close_timestamp de la vela evaluada
    signal: str  # 'BUY' | 'SELL' | 'HOLD'
    strategy_id: str
    strategy_version: str
    indicators: Dict[str, float]
    reference_price: float
    invalidation_level: Optional[float]
    proposed_stop: Optional[float]
    proposed_take_profit: Optional[float]
    explanation: str

    def to_dict(self) -> dict:
        return asdict(self)


class BaseStrategy(ABC):
    strategy_id: str
    strategy_version: str = "1.0.0"
    display_name: str

    @abstractmethod
    def evaluate(
        self,
        candles_1h: List[Candle],
        candles_4h: List[Candle],
        has_open_position: bool = False,
    ) -> StrategySignal:
        """Evalúa exclusivamente velas cerradas disponibles en el instante de decisión."""


class TrendFollowingStrategy(BaseStrategy):
    """Estrategia A: Seguimiento de tendencia (EMA 50/200 4h + EMA 20/50 1h + ATR 14)."""

    strategy_id = "trend_following_v1"
    strategy_version = "1.0.0"
    display_name = "Estrategia A — Seguimiento de Tendencia (EMA 4h/1h + ATR)"

    def evaluate(
        self,
        candles_1h: List[Candle],
        candles_4h: List[Candle],
        has_open_position: bool = False,
    ) -> StrategySignal:
        if not candles_1h:
            raise ValueError("Se requiere al menos una vela 1h cerrada.")
        decision_ts = candles_1h[-1].close_timestamp
        symbol = candles_1h[-1].symbol
        closed_1h, closed_4h = align_4h_to_1h_without_lookahead(
            candles_1h, candles_4h, decision_ts
        )
        ref_price = closed_1h[-1].close

        closes_4h = [c.close for c in closed_4h]
        closes_1h = [c.close for c in closed_1h]

        ema50_4h = calculate_ema(closes_4h, 50)
        ema200_4h = calculate_ema(closes_4h, 200)
        ema20_1h = calculate_ema(closes_1h, 20)
        ema50_1h = calculate_ema(closes_1h, 50)
        atr14_1h = calculate_atr(closed_1h, 14)
        rel_vol = calculate_relative_volume(closed_1h, 20) or 1.0

        if None in (ema50_4h, ema200_4h, ema20_1h, ema50_1h, atr14_1h):
            return StrategySignal(
                symbol=symbol,
                evaluated_at=decision_ts,
                signal="HOLD",
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                indicators={},
                reference_price=ref_price,
                invalidation_level=None,
                proposed_stop=None,
                proposed_take_profit=None,
                explanation="Histórico insuficiente para calcular EMA 200 (4h) o ATR 14 (1h).",
            )

        assert ema50_4h is not None and ema200_4h is not None
        assert ema20_1h is not None and ema50_1h is not None and atr14_1h is not None

        indicators = {
            "ema50_4h": round(ema50_4h, 2),
            "ema200_4h": round(ema200_4h, 2),
            "ema20_1h": round(ema20_1h, 2),
            "ema50_1h": round(ema50_1h, 2),
            "atr14_1h": round(atr14_1h, 2),
            "relative_volume": round(rel_vol, 3),
        }

        trend_favorable = ema50_4h > ema200_4h
        entry_momentum = ema20_1h > ema50_1h and ref_price > ema20_1h
        volatility_ratio = atr14_1h / ref_price

        if has_open_position and (ref_price < ema50_1h or not trend_favorable):
            return StrategySignal(
                symbol=symbol,
                evaluated_at=decision_ts,
                signal="SELL",
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                indicators=indicators,
                reference_price=ref_price,
                invalidation_level=round(ema50_1h, 2),
                proposed_stop=None,
                proposed_take_profit=None,
                explanation="Salida por pérdida de estructura EMA 50 en 1h o agotamiento del filtro 4h.",
            )

        if (
            not has_open_position
            and trend_favorable
            and entry_momentum
            and rel_vol >= 0.90
            and 0.0020 <= volatility_ratio <= 0.035
        ):
            stop_price = round(ref_price - 2.0 * atr14_1h, 2)
            tp_price = round(ref_price + 3.5 * atr14_1h, 2)
            return StrategySignal(
                symbol=symbol,
                evaluated_at=decision_ts,
                signal="BUY",
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                indicators=indicators,
                reference_price=ref_price,
                invalidation_level=round(ema50_1h, 2),
                proposed_stop=stop_price,
                proposed_take_profit=tp_price,
                explanation=(
                    f"Filtro 4h alcista (EMA50={ema50_4h:.1f} > EMA200={ema200_4h:.1f}) y "
                    f"continuación 1h confirmada con volumen relativo {rel_vol:.2f}x."
                ),
            )

        return StrategySignal(
            symbol=symbol,
            evaluated_at=decision_ts,
            signal="HOLD",
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            indicators=indicators,
            reference_price=ref_price,
            invalidation_level=round(ema50_1h, 2),
            proposed_stop=None,
            proposed_take_profit=None,
            explanation="Sin alineación simultánea de tendencia 4h y continuación 1h.",
        )


class MeanReversionStrategy(BaseStrategy):
    """Estrategia B: Reversión a la media con Bandas de Bollinger / Z-Score y filtro de tendencia."""

    strategy_id = "mean_reversion_v1"
    strategy_version = "1.0.0"
    display_name = "Estrategia B — Reversión a la Media (Bollinger + Z-Score)"

    def evaluate(
        self,
        candles_1h: List[Candle],
        candles_4h: List[Candle],
        has_open_position: bool = False,
    ) -> StrategySignal:
        if not candles_1h:
            raise ValueError("Se requiere al menos una vela 1h cerrada.")
        decision_ts = candles_1h[-1].close_timestamp
        symbol = candles_1h[-1].symbol
        closed_1h, closed_4h = align_4h_to_1h_without_lookahead(
            candles_1h, candles_4h, decision_ts
        )
        ref_price = closed_1h[-1].close
        closes_1h = [c.close for c in closed_1h]
        closes_4h = [c.close for c in closed_4h]

        bb = calculate_bollinger_and_zscore(closes_1h, period=20, num_std=2.0)
        atr14 = calculate_atr(closed_1h, 14)
        ema50_4h = calculate_ema(closes_4h, 50)
        ema200_4h = calculate_ema(closes_4h, 200)

        if bb is None or atr14 is None or ema50_4h is None or ema200_4h is None:
            return StrategySignal(
                symbol=symbol,
                evaluated_at=decision_ts,
                signal="HOLD",
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                indicators={},
                reference_price=ref_price,
                invalidation_level=None,
                proposed_stop=None,
                proposed_take_profit=None,
                explanation="Datos insuficientes para Bandas de Bollinger (20) o filtro macro 4h.",
            )

        mean, upper, lower, z_score = bb
        trend_spread_4h = (ema50_4h - ema200_4h) / ema200_4h
        indicators = {
            "bb_mean": round(mean, 2),
            "bb_upper": round(upper, 2),
            "bb_lower": round(lower, 2),
            "z_score": round(z_score, 3),
            "atr14_1h": round(atr14, 2),
            "trend_spread_4h": round(trend_spread_4h, 4),
        }

        # Salida al retornar a la media o superar z >= 0.15
        if has_open_position and (z_score >= 0.15 or ref_price >= mean):
            return StrategySignal(
                symbol=symbol,
                evaluated_at=decision_ts,
                signal="SELL",
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                indicators=indicators,
                reference_price=ref_price,
                invalidation_level=round(mean, 2),
                proposed_stop=None,
                proposed_take_profit=None,
                explanation=f"Retorno a la media alcanzado (Z-Score={z_score:.2f}, media={mean:.1f}).",
            )

        # Evitar operar contra tendencias bajistas fuertes en 4h (trend_spread_4h < -1.5%)
        strong_downtrend = trend_spread_4h < -0.015
        if (
            not has_open_position
            and not strong_downtrend
            and z_score <= -1.85
            and (atr14 / ref_price) <= 0.03
        ):
            stop_price = round(ref_price - 1.8 * atr14, 2)
            tp_price = round(mean, 2)
            return StrategySignal(
                symbol=symbol,
                evaluated_at=decision_ts,
                signal="BUY",
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                indicators=indicators,
                reference_price=ref_price,
                invalidation_level=stop_price,
                proposed_stop=stop_price,
                proposed_take_profit=tp_price,
                explanation=(
                    f"Desviación estadística extrema (Z-Score={z_score:.2f} <= -1.85) sin tendencia "
                    f"bajista severa en 4h (spread={trend_spread_4h*100:.2f}%)."
                ),
            )

        return StrategySignal(
            symbol=symbol,
            evaluated_at=decision_ts,
            signal="HOLD",
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            indicators=indicators,
            reference_price=ref_price,
            invalidation_level=round(lower, 2),
            proposed_stop=None,
            proposed_take_profit=None,
            explanation=f"Z-Score actual ({z_score:.2f}) dentro de banda normal o bloqueado por tendencia.",
        )


class RangeBreakoutStrategy(BaseStrategy):
    """Estrategia C: Ruptura de rangos (Donchian 20 períodos) con filtro de volumen y volatilidad."""

    strategy_id = "range_breakout_v1"
    strategy_version = "1.0.0"
    display_name = "Estrategia C — Ruptura de Rangos (Donchian 20 + Volumen)"

    def evaluate(
        self,
        candles_1h: List[Candle],
        candles_4h: List[Candle],
        has_open_position: bool = False,
    ) -> StrategySignal:
        if not candles_1h:
            raise ValueError("Se requiere al menos una vela 1h cerrada.")
        decision_ts = candles_1h[-1].close_timestamp
        symbol = candles_1h[-1].symbol
        closed_1h, _ = align_4h_to_1h_without_lookahead(
            candles_1h, candles_4h, decision_ts
        )
        ref_price = closed_1h[-1].close

        donchian = calculate_donchian_channel(closed_1h, lookback=20)
        atr14 = calculate_atr(closed_1h, 14)
        rel_vol = calculate_relative_volume(closed_1h, 20)

        if donchian is None or atr14 is None or rel_vol is None:
            return StrategySignal(
                symbol=symbol,
                evaluated_at=decision_ts,
                signal="HOLD",
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                indicators={},
                reference_price=ref_price,
                invalidation_level=None,
                proposed_stop=None,
                proposed_take_profit=None,
                explanation="Histórico insuficiente para canal Donchian (20) o volumen relativo.",
            )

        upper, lower, mid = donchian
        indicators = {
            "donchian_high_20": round(upper, 2),
            "donchian_low_20": round(lower, 2),
            "donchian_mid_20": round(mid, 2),
            "atr14_1h": round(atr14, 2),
            "relative_volume": round(rel_vol, 3),
        }

        if has_open_position and ref_price < mid:
            return StrategySignal(
                symbol=symbol,
                evaluated_at=decision_ts,
                signal="SELL",
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                indicators=indicators,
                reference_price=ref_price,
                invalidation_level=round(mid, 2),
                proposed_stop=None,
                proposed_take_profit=None,
                explanation=f"Cierre por debajo del punto medio del canal Donchian ({mid:.1f}).",
            )

        if not has_open_position and ref_price > upper and rel_vol >= 1.25:
            stop_price = round(max(mid, ref_price - 2.0 * atr14), 2)
            if stop_price >= ref_price:
                stop_price = round(ref_price - 1.5 * atr14, 2)
            tp_price = round(ref_price + 3.2 * atr14, 2)
            return StrategySignal(
                symbol=symbol,
                evaluated_at=decision_ts,
                signal="BUY",
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                indicators=indicators,
                reference_price=ref_price,
                invalidation_level=stop_price,
                proposed_stop=stop_price,
                proposed_take_profit=tp_price,
                explanation=(
                    f"Ruptura de máximo de 20 velas ({upper:.1f}) confirmada con volumen "
                    f"relativo {rel_vol:.2f}x (>= 1.25x)."
                ),
            )

        return StrategySignal(
            symbol=symbol,
            evaluated_at=decision_ts,
            signal="HOLD",
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            indicators=indicators,
            reference_price=ref_price,
            invalidation_level=round(mid, 2),
            proposed_stop=None,
            proposed_take_profit=None,
            explanation="Precio dentro del rango de 20 períodos o ruptura sin volumen suficiente.",
        )


STRATEGY_REGISTRY: Dict[str, BaseStrategy] = {
    TrendFollowingStrategy.strategy_id: TrendFollowingStrategy(),
    MeanReversionStrategy.strategy_id: MeanReversionStrategy(),
    RangeBreakoutStrategy.strategy_id: RangeBreakoutStrategy(),
}
