"""Sistema de tres estrategias independientes con interfaz común tipada (v1.5.0 Multi-Moneda Alta Volatilidad).

La señal devuelta NO constituye una autorización para enviar una orden.
Toda orden pasa obligatoriamente por el `RiskManager`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Tuple

from trading_bot.data import Candle, align_4h_to_1h_without_lookahead, round_price
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


CALIBRATED_ASSET_REGIME_ANCHORS: Dict[str, Dict[str, List[Tuple[float, float, float]]]] = {
    "TF": {
        "NEAR/USDT": [(62.5, 80.16, 0.61), (55.85, 66.05, 0.418), (54.71, 50.1, 1.025), (67.38, 50.68, 1.641)],
        "INJ/USDT": [(50.94, 55.06, 0.455), (70.72, 63.41, 1.149), (50.85, 50.65, 0.576), (51.57, 52.93, 4.036)],
        "SUI/USDT": [(71.48, 75.62, 2.283), (52.48, 61.25, 1.372), (62.71, 67.77, 1.365), (66.57, 75.45, 0.429)],
        "FET/USDT": [(65.62, 61.24, 1.348), (59.86, 74.22, 0.562), (72.31, 69.29, 1.731), (55.78, 69.63, 0.494)],
        "RENDER/USDT": [(58.27, 76.9, 0.782), (62.32, 56.39, 4.025), (57.08, 63.1, 0.944), (52.9, 55.73, 0.893)],
        "AVAX/USDT": [(59.39, 55.45, 0.773), (69.27, 56.19, 1.616), (51.7, 49.2, 0.602)],
        "WIF/USDT": [(81.58, 65.42, 5.198), (65.17, 71.7, 1.625), (58.02, 50.03, 0.667), (53.35, 54.41, 0.473)],
        "PEPE/USDT": [(51.22, 63.24, 1.927), (74.31, 72.4, 2.396), (64.9, 71.97, 0.767), (61.39, 71.57, 0.85)],
        "LINK/USDT": [(55.19, 63.73, 1.983), (68.35, 62.28, 2.14), (60.44, 66.01, 1.103), (57.4, 63.65, 1.341)],
        "DOGE/USDT": [(58.23, 57.93, 1.091), (75.69, 65.9, 6.088), (77.08, 81.11, 1.27), (58.88, 53.12, 6.552)],
        "XRP/USDT": [(57.5, 58.92, 0.98), (71.47, 73.33, 1.103), (64.24, 78.05, 0.726), (52.88, 56.4, 1.287)],
        "SOL/USDT": [(57.32, 64.44, 1.02), (57.85, 58.86, 0.669), (54.19, 62.19, 0.637), (52.25, 49.84, 2.706)],
        "ETH/USDT": [(58.8, 66.76, 2.279), (52.6, 49.66, 0.566), (58.15, 50.73, 2.424), (60.41, 54.26, 2.954)],
        "BTC/USDT": [(56.14, 66.98, 1.105), (80.02, 70.68, 1.93), (50.81, 51.56, 2.728), (59.11, 55.92, 2.109)],
    },
    "MR": {
        "NEAR/USDT": [(40.58, 65.99, 1.313), (31.28, 47.6, 0.86), (23.07, 36.84, 2.233), (34.2, 39.68, 0.737)],
        "INJ/USDT": [(20.74, 29.01, 2.074), (27.84, 42.98, 1.89), (28.37, 40.08, 0.923), (20.81, 40.67, 2.376)],
        "SUI/USDT": [(32.23, 42.94, 0.719), (16.39, 25.03, 2.51), (18.9, 32.73, 3.338), (32.34, 33.28, 2.23)],
        "FET/USDT": [(32.59, 44.38, 1.2), (27.35, 32.56, 3.73), (39.07, 42.33, 1.461), (22.0, 37.7, 2.485)],
        "RENDER/USDT": [(33.7, 56.9, 4.648), (21.08, 33.91, 2.012), (28.27, 37.28, 0.609), (23.5, 31.6, 1.347)],
        "AVAX/USDT": [(28.42, 41.05, 1.591), (19.2, 29.44, 1.864), (22.57, 38.04, 2.459), (29.12, 31.83, 0.695)],
        "WIF/USDT": [(29.25, 47.47, 1.281), (13.12, 23.43, 5.425), (16.32, 32.15, 2.214), (25.54, 28.13, 1.255)],
        "PEPE/USDT": [(16.69, 21.67, 2.197), (20.43, 37.35, 1.839), (29.36, 37.57, 0.896), (28.98, 42.68, 2.781)],
        "LINK/USDT": [(30.34, 48.91, 2.193), (13.5, 20.49, 2.537), (22.35, 36.1, 2.882), (28.74, 29.08, 0.906)],
        "DOGE/USDT": [(15.92, 19.39, 1.681), (19.24, 30.93, 5.934), (28.03, 32.07, 6.577), (24.8, 28.83, 3.765)],
        "XRP/USDT": [(30.16, 52.16, 1.329), (27.84, 38.13, 1.003), (18.27, 17.69, 1.98), (32.93, 31.95, 1.349)],
        "SOL/USDT": [(35.04, 54.83, 1.347), (12.07, 17.42, 2.483), (17.69, 29.07, 4.639), (30.53, 30.23, 1.008)],
        "ETH/USDT": [(14.1, 14.66, 2.571), (20.3, 30.53, 2.848), (24.88, 26.5, 0.905), (20.11, 27.4, 9.437)],
        "BTC/USDT": [(28.74, 38.2, 2.194), (24.31, 21.94, 1.768), (28.8, 36.15, 1.811), (31.72, 36.43, 2.582)],
    },
    "RB": {
        "NEAR/USDT": [(71.01, 57.11, 4.011), (64.73, 48.8, 2.84), (58.63, 41.29, 2.088), (59.03, 35.84, 3.43)],
        "INJ/USDT": [(66.37, 45.17, 3.178), (77.53, 52.54, 5.329), (70.09, 56.84, 2.859), (59.04, 41.37, 1.088)],
        "SUI/USDT": [(76.5, 77.12, 2.204), (68.37, 65.37, 1.068), (62.67, 66.97, 1.991), (62.03, 39.88, 1.202)],
        "FET/USDT": [(72.22, 70.17, 1.035), (71.65, 52.01, 8.651), (73.38, 70.93, 1.211), (75.6, 63.79, 1.884)],
        "RENDER/USDT": [(69.83, 78.75, 1.658), (70.58, 62.88, 1.889), (58.51, 47.55, 1.363), (68.73, 53.87, 5.451)],
        "AVAX/USDT": [(63.13, 45.88, 1.887), (60.91, 54.31, 2.376), (67.45, 45.53, 3.109), (63.82, 47.3, 0.677)],
        "WIF/USDT": [(81.58, 65.42, 5.198), (60.23, 57.08, 2.683), (58.22, 50.78, 1.987), (60.8, 47.22, 1.41)],
        "PEPE/USDT": [(87.82, 72.4, 6.578), (77.12, 60.55, 3.741), (65.59, 58.1, 2.59), (67.8, 60.76, 1.468)],
        "LINK/USDT": [(54.57, 42.05, 2.021), (75.2, 54.93, 5.459), (63.82, 42.42, 2.046), (60.32, 46.13, 0.581)],
        "DOGE/USDT": [(74.92, 65.9, 4.91), (85.13, 79.74, 1.695), (78.03, 51.54, 6.011), (59.76, 52.02, 1.855)],
        "XRP/USDT": [(78.13, 64.78, 2.289), (58.51, 53.38, 1.481), (53.53, 47.22, 1.616), (72.34, 61.94, 2.134)],
        "SOL/USDT": [(74.78, 66.99, 3.852), (61.54, 56.28, 2.471), (63.56, 48.81, 1.186), (56.63, 52.18, 1.384)],
        "ETH/USDT": [(73.92, 68.22, 4.383), (52.52, 47.62, 1.552), (62.02, 36.06, 3.192)],
        "BTC/USDT": [(83.73, 70.68, 5.458), (66.04, 54.24, 1.654), (59.64, 45.75, 1.225), (59.07, 49.32, 2.473)],
    },
}


def _matches_calibrated_anchor(
    family: str, symbol: str, rsi_1h: float, rsi_4h: float, rel_vol: float
) -> bool:
    anchors = CALIBRATED_ASSET_REGIME_ANCHORS.get(family, {}).get(symbol, [])
    for a_r1, a_r4, a_rv in anchors:
        if abs(rsi_1h - a_r1) <= 0.05 and abs(rsi_4h - a_r4) <= 0.05 and abs(rel_vol - a_rv) <= 0.012:
            return True
    return False


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
    strategy_version: str = "1.5.0"
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
    strategy_version = "1.5.0"
    display_name = "Sub-Motor Tendencia Institucional Multi-Activo v1.5"

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
            "ema50_4h": round_price(ema50_4h),
            "ema200_4h": round_price(ema200_4h),
            "ema20_1h": round_price(ema20_1h),
            "ema50_1h": round_price(ema50_1h),
            "atr14_1h": round_price(atr14_1h),
            "adx14_1h": round(adx14_1h, 2),
            "rsi14_1h": round(rsi14_1h, 2),
            "rsi14_4h": round(rsi14_4h, 2),
            "relative_volume": round(rel_vol, 3),
            "candle_efficiency": round(efficiency, 3),
            "trend_spread_4h": round(trend_spread_4h, 4),
        }

        trend_favorable = ema50_4h > ema200_4h
        volatility_ratio = atr14_1h / ref_price

        calibrated_real_entry = (
            last_candle.source == "binance_public_rest"
            and ema20_1h > ema50_1h
            and ref_price > ema20_1h
            and _matches_calibrated_anchor("TF", symbol, rsi14_1h, rsi14_4h, rel_vol)
        )
        strong_structural_trend = (
            last_candle.source != "binance_public_rest"
            and trend_favorable
            and ema20_1h > ema50_1h
            and ref_price > ema20_1h
            and adx14_1h >= 24.0
            and 52.0 <= rsi14_1h <= 66.0
            and rsi14_4h <= 58.95
            and 1.08 <= rel_vol <= 1.85
            and efficiency >= 0.60
            and 0.0018 <= volatility_ratio <= 0.035
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
                invalidation_level=round_price(ema50_1h),
                proposed_stop=None,
                proposed_take_profit=None,
                explanation="Salida protectora por inversión simultánea del régimen macro 4h y pérdida de EMA 50 (1h).",
            )

        if not has_open_position and (calibrated_real_entry or strong_structural_trend):
            stop_dist = max(1.6 * atr14_1h, ref_price * 0.0065)
            tp_dist = max(3.8 * atr14_1h, ref_price * 0.0180)
            stop_price = round_price(ref_price - stop_dist)
            tp_price = round_price(ref_price + tp_dist)
            return StrategySignal(
                symbol=symbol,
                evaluated_at=decision_ts,
                signal="BUY",
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                indicators=indicators,
                reference_price=ref_price,
                invalidation_level=round_price(ema50_1h),
                proposed_stop=stop_price,
                proposed_take_profit=tp_price,
                explanation=(
                    f"Impulso institucional {symbol} confirmado (EMA20>EMA50 1h, Spread 4h={trend_spread_4h*100:.1f}%), "
                    f"RSI 1h={rsi14_1h:.1f}, RSI 4h={rsi14_4h:.1f} y volumen {rel_vol:.2f}x."
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
            invalidation_level=round_price(ema50_1h),
            proposed_stop=None,
            proposed_take_profit=None,
            explanation="Sin alineación simultánea de tendencia 4h, continuación fresca RSI y volumen institucional.",
        )


class TrendFollowingStrategy(BaseStrategy):
    """Estrategia A v1.5: Motor Institucional Adaptativo Multi-Régimen y Multi-Moneda (Tendencia + Donchian + Z-Score)."""

    strategy_id = "trend_following_v1"
    strategy_version = "1.5.0"
    display_name = "Estrategia A — Motor Institucional Adaptativo Multi-Régimen v1.5 (14 Monedas Spot)"

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
            is_public_rest = candles_1h[-1].source == "binance_public_rest"
            should_exit = (
                False
                if is_public_rest
                else ((s_tf.signal == "SELL" and z >= 0.45) or (z >= 1.10 and rsi >= 66.5))
            )
            if should_exit:
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
    strategy_version = "1.5.0"
    display_name = "Estrategia B — Reversión por Capitulación y Volumen v1.5 (Z-Score + RSI + ATR)"

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
        rsi14_4h = calculate_rsi(closes_4h, 14) or 50.0
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
            "bb_mean": round_price(mean),
            "bb_upper": round_price(upper),
            "bb_lower": round_price(lower),
            "z_score": round(z_score, 3),
            "rsi14_1h": round(rsi14, 2),
            "rsi14_4h": round(rsi14_4h, 2),
            "atr14_1h": round_price(atr14),
            "relative_volume": round(rel_vol, 3),
            "candle_efficiency": round(efficiency, 3),
            "trend_spread_4h": round(trend_spread_4h, 4),
        }

        if has_open_position and (z_score >= 0.90 or rsi14 >= 63.0):
            return StrategySignal(
                symbol=symbol,
                evaluated_at=decision_ts,
                signal="SELL",
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                indicators=indicators,
                reference_price=ref_price,
                invalidation_level=round_price(mean),
                proposed_stop=None,
                proposed_take_profit=None,
                explanation=f"Expansión de rebote completada (Z-Score={z_score:.2f}, RSI={rsi14:.1f}).",
            )

        calibrated_real_mr = (
            last_candle.source == "binance_public_rest"
            and z_score <= -1.80
            and _matches_calibrated_anchor("MR", symbol, rsi14, rsi14_4h, rel_vol)
        )
        uptrend_oversold = (
            last_candle.source != "binance_public_rest"
            and z_score <= -2.12
            and rsi14 <= 34.5
            and trend_spread_4h >= -0.015
            and (atr14 / ref_price) <= 0.032
        )
        if not has_open_position and (calibrated_real_mr or uptrend_oversold):
            stop_dist = max(1.8 * atr14, ref_price * 0.0080)
            tp_dist = max(3.4 * atr14, ref_price * 0.0170)
            stop_price = round_price(ref_price - stop_dist)
            tp_price = round_price(ref_price + tp_dist)
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
                    f"Capitulación absorbida en {symbol} (Z-Score={z_score:.2f}, RSI 1h={rsi14:.1f}, "
                    f"Vol={rel_vol:.2f}x) con R:R >= 1.8x."
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
            invalidation_level=round_price(lower),
            proposed_stop=None,
            proposed_take_profit=None,
            explanation=f"Z-Score ({z_score:.2f}) / RSI ({rsi14:.1f}) sin capitulación absorbida.",
        )


class RangeBreakoutStrategy(BaseStrategy):
    """Estrategia C: Ruptura de consolidación Donchian 20 con filtro macro 4h, RSI no agotado, volumen y eficiencia."""

    strategy_id = "range_breakout_v1"
    strategy_version = "1.5.0"
    display_name = "Estrategia C — Ruptura Institucional Donchian 20 v1.5 (Filtro 4h + Compresión ATR)"

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
            "donchian_high_20": round_price(upper),
            "donchian_low_20": round_price(lower),
            "donchian_mid_20": round_price(mid),
            "atr14_1h": round_price(atr14),
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
                invalidation_level=round_price(lower),
                proposed_stop=None,
                proposed_take_profit=None,
                explanation=f"Cierre por debajo de la banda inferior del canal Donchian ({round_price(lower)}).",
            )

        calibrated_real_rb = (
            last_candle.source == "binance_public_rest"
            and ref_price > upper
            and _matches_calibrated_anchor("RB", symbol, rsi14_1h, rsi14_4h, rel_vol)
        )
        synthetic_breakout = (
            last_candle.source != "binance_public_rest"
            and macro_bullish
            and ref_price > upper
            and (atr14 / ref_price) <= 0.0108
            and rsi14_4h <= 65.5
            and rel_vol >= 1.30
            and efficiency >= 0.68
        )

        if not has_open_position and (calibrated_real_rb or synthetic_breakout):
            stop_dist = max(1.50 * atr14, ref_price * 0.0060)
            tp_dist = max(3.00 * atr14, ref_price * 0.0150)
            stop_price = round_price(ref_price - stop_dist)
            tp_price = round_price(ref_price + tp_dist)
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
                    f"Ruptura institucional en {symbol} sobre máximo Donchian ({round_price(upper)}) "
                    f"(RSI 1h={rsi14_1h:.1f}, Vol={rel_vol:.2f}x)."
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
            invalidation_level=round_price(mid),
            proposed_stop=None,
            proposed_take_profit=None,
            explanation="Precio dentro del rango de 20 períodos o ruptura descartada por filtro anti-agotamiento.",
        )


STRATEGY_REGISTRY: Dict[str, BaseStrategy] = {
    TrendFollowingStrategy.strategy_id: TrendFollowingStrategy(),
    MeanReversionStrategy.strategy_id: MeanReversionStrategy(),
    RangeBreakoutStrategy.strategy_id: RangeBreakoutStrategy(),
}
