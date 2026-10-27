"""Cálculo determinista de indicadores técnicos sobre velas cerradas.

Nunca utiliza datos futuros y devuelve `None` cuando el histórico es insuficiente.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from trading_bot.data import Candle


def calculate_sma(values: List[float], period: int) -> Optional[float]:
    if period <= 0 or len(values) < period:
        return None
    window = values[-period:]
    if any(math.isnan(v) or math.isinf(v) for v in window):
        return None
    return sum(window) / period


def calculate_ema_series(values: List[float], period: int) -> List[Optional[float]]:
    if period <= 0 or len(values) < period:
        return [None] * len(values)
    result: List[Optional[float]] = [None] * len(values)
    seed = sum(values[:period]) / period
    result[period - 1] = seed
    k = 2.0 / (period + 1.0)
    prev = seed
    for idx in range(period, len(values)):
        val = values[idx]
        if math.isnan(val) or math.isinf(val):
            return [None] * len(values)
        curr = (val - prev) * k + prev
        result[idx] = curr
        prev = curr
    return result


def calculate_ema(values: List[float], period: int) -> Optional[float]:
    series = calculate_ema_series(values, period)
    return series[-1] if series else None


def calculate_atr(candles: List[Candle], period: int = 14) -> Optional[float]:
    """Calcula el Average True Range (ATR) de Wilder sobre velas cerradas."""
    closed = [c for c in candles if c.is_closed]
    if period <= 0 or len(closed) < period + 1:
        return None
    trs: List[float] = []
    for i in range(1, len(closed)):
        curr = closed[i]
        prev_close = closed[i - 1].close
        tr = max(
            curr.high - curr.low,
            abs(curr.high - prev_close),
            abs(curr.low - prev_close),
        )
        trs.append(tr)

    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr


def calculate_bollinger_and_zscore(
    closes: List[float], period: int = 20, num_std: float = 2.0
) -> Optional[Tuple[float, float, float, float]]:
    """Devuelve (media, banda_superior, banda_inferior, z_score)."""
    if period <= 1 or len(closes) < period:
        return None
    window = closes[-period:]
    mean = sum(window) / period
    variance = sum((x - mean) ** 2 for x in window) / period
    std = math.sqrt(variance)
    if std <= 1e-12:
        return (mean, mean, mean, 0.0)
    upper = mean + num_std * std
    lower = mean - num_std * std
    z_score = (closes[-1] - mean) / std
    return (mean, upper, lower, z_score)


def calculate_relative_volume(candles: List[Candle], period: int = 20) -> Optional[float]:
    closed = [c for c in candles if c.is_closed]
    if period <= 0 or len(closed) < period + 1:
        return None
    avg_vol = sum(c.volume for c in closed[-(period + 1) : -1]) / period
    if avg_vol <= 0:
        return None
    return closed[-1].volume / avg_vol


def calculate_donchian_channel(
    candles: List[Candle], lookback: int = 20
) -> Optional[Tuple[float, float, float]]:
    """Calcula el canal de máximos/mínimos de las `lookback` velas cerradas ANTERIORES a la vela actual."""
    closed = [c for c in candles if c.is_closed]
    if lookback <= 0 or len(closed) < lookback + 1:
        return None
    prior_window = closed[-(lookback + 1) : -1]
    upper = max(c.high for c in prior_window)
    lower = min(c.low for c in prior_window)
    mid = (upper + lower) / 2.0
    return (upper, lower, mid)
