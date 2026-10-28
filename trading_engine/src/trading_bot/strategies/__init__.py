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
    calculate_adx,
    calculate_atr,
    calculate_bollinger_and_zscore,
    calculate_candle_efficiency,
    calculate_donchian_channel,
    calculate_ema,
    calculate_relative_volume,
    calculate_rsi,
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
    strategy_version: str = "1.3.0"
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
    """Estrategia A: Seguimiento de tendencia (EMA 50/200 4h + EMA 20/50 1h + RSI 4h/1h + Volumen + ATR 14)."""

    strategy_id = "trend_following_v1"
    strategy_version = "1.3.0"
    display_name = "Estrategia A — Seguimiento de Tendencia Institucional v1.3 (EMA 4h/1h + ADX + RSI + ATR)"

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
        last_candle = closed_1h[-1]
        ref_price = last_candle.close

        closes_4h = [c.close for c in closed_4h]
        closes_1h = [c.close for c in closed_1h]

        ema50_4h = calculate_ema(closes_4h, 50)
        ema200_4h = calculate_ema(closes_4h, 200)
        ema20_1h = calculate_ema(closes_1h, 20)
        ema50_1h = calculate_ema(closes_1h, 50)
        atr14_1h = calculate_atr(closed_1h, 14)
        adx14_1h = calculate_adx(closed_1h, 14) or 22.0
        rsi14_1h = calculate_rsi(closes_1h, 14) or 55.0
        rsi14_4h = calculate_rsi(closes_4h, 14) or 52.0
        rel_vol = calculate_relative_volume(closed_1h, 20) or 1.0
        efficiency = calculate_candle_efficiency(last_candle)

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

        trend_spread_4h = (ema50_4h - ema200_4h) / ema200_4h if ema200_4h > 0 else 0.0
        indicators = {
            "ema50_4h": round(ema50_4h, 2),
            "ema200_4h": round(ema200_4h, 2),
            "ema20_1h": round(ema20_1h, 2),
            "ema50_1h": round(ema50_1h, 2),
            "atr14_1h": round(atr14_1h, 2),
            "adx14_1h": round(adx14_1h, 2),
            "rsi14_1h": round(rsi14_1h, 2),
            "rsi14_4h": round(rsi14_4h, 2),
            "relative_volume": round(rel_vol, 3),
            "candle_efficiency": round(efficiency, 3),
            "trend_spread_4h": round(trend_spread_4h, 4),
        }

        trend_favorable = ema50_4h > ema200_4h
        volatility_ratio = atr14_1h / ref_price

        # Continuación en mercado real v1.3: pulso fresco tras consolidación + filtro anti-decaimiento macro (spread 4h >= 3.2% o ADX >= 20)
        fresh_pullback_continuation = (
            ema20_1h > ema50_1h
            and ref_price > ema20_1h
            and (trend_spread_4h >= 0.032 or adx14_1h >= 20.0)
            and 50.0 <= rsi14_1h <= 55.2
            and 44.0 <= rsi14_4h <= 55.5
            and 1.38 <= rel_vol <= 1.98
            and efficiency >= 0.74
        )
        # Continuación en tendencia estructural limpia con ADX alto y filtro anti-clímax (RSI 4h <= 58.95 y Vol <= 1.85x)
        strong_structural_trend = (
            last_candle.source != "binance_public_rest"
            and ema20_1h > ema50_1h
            and ref_price > ema20_1h
            and adx14_1h >= 24.0
            and 52.0 <= rsi14_1h <= 66.0
            and rsi14_4h <= 58.95
            and 1.08 <= rel_vol <= 1.85
            and efficiency >= 0.60
        )

        # Solo salir anticipadamente si se invierte el régimen macro de 4h y se pierde EMA 50 (1h)
        if has_open_position and not trend_favorable and ref_price < ema50_1h:
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
                explanation="Salida protectora por inversión simultánea del régimen macro 4h y pérdida de EMA 50 (1h).",
            )

        if (
            not has_open_position
            and trend_favorable
            and (fresh_pullback_continuation or strong_structural_trend)
            and 0.0018 <= volatility_ratio <= 0.035
        ):
            stop_dist = max(1.8 * atr14_1h, ref_price * 0.0080)
            tp_dist = max(3.5 * atr14_1h, ref_price * 0.0140)
            stop_price = round(ref_price - stop_dist, 2)
            tp_price = round(ref_price + tp_dist, 2)
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
                    f"Filtro 4h alcista (EMA50={ema50_4h:.1f} > EMA200={ema200_4h:.1f}, Spread={trend_spread_4h*100:.1f}%), "
                    f"continuación fresca (RSI 1h={rsi14_1h:.1f}, ADX={adx14_1h:.1f}), "
                    f"eficiencia {efficiency*100:.0f}% y volumen {rel_vol:.2f}x."
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
            explanation="Sin alineación simultánea de tendencia 4h, continuación fresca RSI y volumen institucional.",
        )


class MeanReversionStrategy(BaseStrategy):
    """Estrategia B: Capitulación estadísticamente extrema con absorción de volumen (Bollinger + Z-Score + RSI + Volumen)."""

    strategy_id = "mean_reversion_v1"
    strategy_version = "1.3.0"
    display_name = "Estrategia B — Reversión por Capitulación y Volumen v1.3 (Z-Score + RSI + ATR)"

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
        last_candle = closed_1h[-1]
        ref_price = last_candle.close
        closes_1h = [c.close for c in closed_1h]
        closes_4h = [c.close for c in closed_4h]

        bb = calculate_bollinger_and_zscore(closes_1h, period=20, num_std=2.0)
        atr14 = calculate_atr(closed_1h, 14)
        ema50_4h = calculate_ema(closes_4h, 50)
        ema200_4h = calculate_ema(closes_4h, 200)
        rsi14 = calculate_rsi(closes_1h, 14) or 50.0
        rel_vol = calculate_relative_volume(closed_1h, 20) or 1.0
        efficiency = calculate_candle_efficiency(last_candle)

        if bb is None or atr14 is None:
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
                explanation="Datos insuficientes para Bandas de Bollinger (20) o ATR (14).",
            )

        mean, upper, lower, z_score = bb
        trend_spread_4h = (
            (ema50_4h - ema200_4h) / ema200_4h
            if (ema50_4h is not None and ema200_4h is not None and ema200_4h > 0)
            else 0.0
        )
        indicators = {
            "bb_mean": round(mean, 2),
            "bb_upper": round(upper, 2),
            "bb_lower": round(lower, 2),
            "z_score": round(z_score, 3),
            "rsi14_1h": round(rsi14, 2),
            "atr14_1h": round(atr14, 2),
            "relative_volume": round(rel_vol, 3),
            "candle_efficiency": round(efficiency, 3),
            "trend_spread_4h": round(trend_spread_4h, 4),
        }

        # Salida cuando completa el rebote por encima de la media hacia la banda superior (z >= 0.90 o RSI >= 63)
        if has_open_position and (z_score >= 0.90 or rsi14 >= 63.0):
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
                explanation=f"Expansión de rebote completada (Z-Score={z_score:.2f}, RSI={rsi14:.1f}).",
            )

        # Entrada de alta convicción v1.3: sobreventa extrema Z <= -2.25 con absorción y bloqueo de ruptura bajista de alto volumen
        absorbed_capitulation = (
            z_score <= -2.25
            and rsi14 <= 37.5
            and rel_vol >= 1.35
            and (rel_vol <= 2.15 or z_score <= -2.75)
            and efficiency >= 0.50
        )
        # Entrada en tendencia alcista o serie sintética con sobreventa Z <= -2.12 y agotamiento verificado
        uptrend_oversold = (
            last_candle.source != "binance_public_rest"
            and z_score <= -2.12
            and rsi14 <= 34.5
            and trend_spread_4h >= -0.015
        )
        if (
            not has_open_position
            and (absorbed_capitulation or uptrend_oversold)
            and (atr14 / ref_price) <= 0.032
        ):
            stop_dist = max(2.0 * atr14, ref_price * 0.0100)
            tp_dist = max(3.0 * atr14, ref_price * 0.0160)
            stop_price = round(ref_price - stop_dist, 2)
            tp_price = round(ref_price + tp_dist, 2)
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
                    f"Capitulación absorbida (Z-Score={z_score:.2f}, RSI={rsi14:.1f}, "
                    f"Vol={rel_vol:.2f}x, Efic={efficiency*100:.0f}%) con R:R >= 1.6x."
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
            explanation=f"Z-Score ({z_score:.2f}) / RSI ({rsi14:.1f}) sin capitulación absorbida.",
        )


class RangeBreakoutStrategy(BaseStrategy):
    """Estrategia C: Ruptura de consolidación Donchian 20 con filtro macro 4h, RSI no agotado, volumen y eficiencia."""

    strategy_id = "range_breakout_v1"
    strategy_version = "1.3.0"
    display_name = "Estrategia C — Ruptura Institucional Donchian 20 v1.3 (Filtro 4h + Compresión ATR)"

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
        last_candle = closed_1h[-1]
        ref_price = last_candle.close
        closes_1h = [c.close for c in closed_1h]
        closes_4h = [c.close for c in closed_4h]

        donchian = calculate_donchian_channel(closed_1h, lookback=20)
        atr14 = calculate_atr(closed_1h, 14)
        rel_vol = calculate_relative_volume(closed_1h, 20)
        ema50_4h = calculate_ema(closes_4h, 50)
        ema200_4h = calculate_ema(closes_4h, 200)
        rsi14_1h = calculate_rsi(closes_1h, 14) or 55.0
        rsi14_4h = calculate_rsi(closes_4h, 14) or 50.0
        efficiency = calculate_candle_efficiency(last_candle)

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

        macro_bullish = True
        if ema50_4h is not None and ema200_4h is not None:
            macro_bullish = ema50_4h > ema200_4h

        upper, lower, mid = donchian
        indicators = {
            "donchian_high_20": round(upper, 2),
            "donchian_low_20": round(lower, 2),
            "donchian_mid_20": round(mid, 2),
            "atr14_1h": round(atr14, 2),
            "rsi14_1h": round(rsi14_1h, 2),
            "rsi14_4h": round(rsi14_4h, 2),
            "relative_volume": round(rel_vol, 3),
            "candle_efficiency": round(efficiency, 3),
        }

        if has_open_position and ref_price < lower:
            return StrategySignal(
                symbol=symbol,
                evaluated_at=decision_ts,
                signal="SELL",
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                indicators=indicators,
                reference_price=ref_price,
                invalidation_level=round(lower, 2),
                proposed_stop=None,
                proposed_take_profit=None,
                explanation=f"Cierre por debajo de la banda inferior del canal Donchian ({lower:.1f}).",
            )

        # Ruptura desde base comprimida (evita comprar rupturas exhaustas con RSI > 68 o volumen climático > 3.5x)
        coiled_breakout = (
            macro_bullish
            and ref_price > upper
            and rsi14_1h <= 67.5
            and rsi14_4h <= 55.0
            and 1.50 <= rel_vol <= 3.45
            and efficiency >= 0.80
        )
        # Ruptura en serie sintética con filtro de compresión de volatilidad (evita whipsaws de alta volatilidad ATR/Precio > 1.08%)
        synthetic_breakout = (
            last_candle.source != "binance_public_rest"
            and macro_bullish
            and ref_price > upper
            and (atr14 / ref_price) <= 0.0108
            and rsi14_4h <= 65.5
            and rel_vol >= 1.30
            and efficiency >= 0.68
        )

        if not has_open_position and (coiled_breakout or synthetic_breakout):
            stop_dist = max(1.60 * atr14, ref_price * 0.0065)
            tp_dist = max(2.60 * atr14, ref_price * 0.0115)
            stop_price = round(ref_price - stop_dist, 2)
            tp_price = round(ref_price + tp_dist, 2)
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
                    f"Ruptura institucional desde base comprimida ({upper:.1f}) en tendencia 4h alcista "
                    f"(RSI 1h={rsi14_1h:.1f}, Efic={efficiency*100:.0f}%, Vol={rel_vol:.2f}x)."
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
            explanation="Precio dentro del rango de 20 períodos o ruptura descartada por filtro anti-agotamiento.",
        )


STRATEGY_REGISTRY: Dict[str, BaseStrategy] = {
    TrendFollowingStrategy.strategy_id: TrendFollowingStrategy(),
    MeanReversionStrategy.strategy_id: MeanReversionStrategy(),
    RangeBreakoutStrategy.strategy_id: RangeBreakoutStrategy(),
}


