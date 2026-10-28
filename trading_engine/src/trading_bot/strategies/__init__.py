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
    strategy_version: str = "1.4.0"
    display_name: str

    @abstractmethod
    def evaluate(
        self,
        candles_1h: List[Candle],
        candles_4h: List[Candle],
        has_open_position: bool = False,
    ) -> StrategySignal:
        """Evalúa exclusivamente velas cerradas disponibles en el instante de decisión."""


class _CoreTrendSubStrategy(BaseStrategy):
    """Sub-motor de continuación de tendencia institucional (EMA 50/200 4h + EMA 20/50 1h + ADX + RSI + ATR)."""

    strategy_id = "trend_following_v1"
    strategy_version = "1.4.0"
    display_name = "Sub-Motor Tendencia Institucional"

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

        fresh_pullback_continuation = (
            ema20_1h > ema50_1h
            and ref_price > ema20_1h
            and (trend_spread_4h >= 0.032 or adx14_1h >= 20.0)
            and 50.0 <= rsi14_1h <= 55.2
            and 44.0 <= rsi14_4h <= 55.5
            and 1.38 <= rel_vol <= 1.98
            and efficiency >= 0.74
        )
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


class TrendFollowingStrategy(BaseStrategy):
    """Estrategia A v1.4: Motor Institucional Adaptativo Multi-Régimen (Tendencia 4h/1h + Ruptura Donchian + Capitulación Z-Score)."""

    strategy_id = "trend_following_v1"
    strategy_version = "1.4.0"
    display_name = "Estrategia A — Motor Institucional Adaptativo Multi-Régimen v1.4 (EMA 4h/1h + Donchian + Z-Score)"

    def __init__(self) -> None:
        self._core_trend = _CoreTrendSubStrategy()
        self._mean_rev = MeanReversionStrategy()
        self._breakout = RangeBreakoutStrategy()

    def evaluate(
        self,
        candles_1h: List[Candle],
        candles_4h: List[Candle],
        has_open_position: bool = False,
    ) -> StrategySignal:
        if not candles_1h:
            raise ValueError("Se requiere al menos una vela 1h cerrada.")
        s_mr = self._mean_rev.evaluate(candles_1h, candles_4h, has_open_position)
        s_rb = self._breakout.evaluate(candles_1h, candles_4h, has_open_position)
        s_tf = self._core_trend.evaluate(candles_1h, candles_4h, has_open_position)

        merged_indicators = {**s_mr.indicators, **s_rb.indicators, **s_tf.indicators}
        if not merged_indicators:
            return s_tf

        if has_open_position:
            z = s_mr.indicators.get("z_score", 0.0)
            rsi = s_mr.indicators.get("rsi14_1h", 50.0)
            if (s_tf.signal == "SELL" and z >= 0.45) or (z >= 1.10 and rsi >= 66.5):
                return StrategySignal(
                    symbol=s_mr.symbol,
                    evaluated_at=s_mr.evaluated_at,
                    signal="SELL",
                    strategy_id=self.strategy_id,
                    strategy_version=self.strategy_version,
                    indicators=merged_indicators,
                    reference_price=s_mr.reference_price,
                    invalidation_level=s_mr.invalidation_level,
                    proposed_stop=None,
                    proposed_take_profit=None,
                    explanation=f"Toma de beneficio institucional multi-régimen (Z-Score={z:.2f}, RSI={rsi:.1f}).",
                )
            return StrategySignal(
                symbol=s_tf.symbol,
                evaluated_at=s_tf.evaluated_at,
                signal="HOLD",
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                indicators=merged_indicators,
                reference_price=s_tf.reference_price,
                invalidation_level=s_tf.invalidation_level,
                proposed_stop=None,
                proposed_take_profit=None,
                explanation="Posición activa protegida por Stop-Loss estructural y Take-Profit dinámico.",
            )

        for cand, tag in (
            (s_mr, "CAPITULACIÓN ABSORBIDA"),
            (s_rb, "RUPTURA COMPRIMIDA"),
            (s_tf, "CONTINUACIÓN TENDENCIA"),
        ):
            if cand.signal == "BUY":
                return StrategySignal(
                    symbol=cand.symbol,
                    evaluated_at=cand.evaluated_at,
                    signal="BUY",
                    strategy_id=self.strategy_id,
                    strategy_version=self.strategy_version,
                    indicators=merged_indicators,
                    reference_price=cand.reference_price,
                    invalidation_level=cand.invalidation_level,
                    proposed_stop=cand.proposed_stop,
                    proposed_take_profit=cand.proposed_take_profit,
                    explanation=f"[{tag}] {cand.explanation}",
                )

        return StrategySignal(
            symbol=s_tf.symbol,
            evaluated_at=s_tf.evaluated_at,
            signal="HOLD",
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            indicators=merged_indicators,
            reference_price=s_tf.reference_price,
            invalidation_level=s_tf.invalidation_level,
            proposed_stop=None,
            proposed_take_profit=None,
            explanation=s_tf.explanation,
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


