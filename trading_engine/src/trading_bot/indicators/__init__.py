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


def calculate_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """Calcula el RSI suavizado de Wilder (0 a 100) sobre precios de cierre."""
    if period <= 0 or len(closes) < period + 1:
        return None
    tail = closes[-(period * 3 + 5) :]
    gains: List[float] = []
    losses: List[float] = []
    for i in range(1, len(tail)):
        delta = tail[i] - tail[i - 1]
        if math.isnan(delta) or math.isinf(delta):
            return None
        gains.append(max(0.0, delta))
        losses.append(max(0.0, -delta))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for idx in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[idx]) / period
        avg_loss = (avg_loss * (period - 1) + losses[idx]) / period

    if avg_loss <= 1e-12:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def calculate_adx(candles: List[Candle], period: int = 14) -> Optional[float]:
    """Calcula el Average Directional Index (ADX) de Wilder para filtrar mercados laterales sin fuerza."""
    if period <= 0 or len(candles) < (period * 2 + 1):
        return None
    tail_raw = candles[-(period * 3 + 10) :]
    closed = [c for c in tail_raw if c.is_closed]
    if len(closed) < (period * 2 + 1):
        return None

    tr_list: List[float] = []
    plus_dm_list: List[float] = []
    minus_dm_list: List[float] = []

    for i in range(1, len(closed)):
        curr = closed[i]
        prev = closed[i - 1]
        up_move = curr.high - prev.high
        down_move = prev.low - curr.low
        plus_dm = up_move if (up_move > down_move and up_move > 0) else 0.0
        minus_dm = down_move if (down_move > up_move and down_move > 0) else 0.0
        tr = max(
            curr.high - curr.low,
            abs(curr.high - prev.close),
            abs(curr.low - prev.close),
        )
        tr_list.append(tr)
        plus_dm_list.append(plus_dm)
        minus_dm_list.append(minus_dm)

    sm_tr = sum(tr_list[:period])
    sm_plus = sum(plus_dm_list[:period])
    sm_minus = sum(minus_dm_list[:period])

    dx_values: List[float] = []
    for idx in range(period, len(tr_list)):
        if idx > period:
            sm_tr = sm_tr - (sm_tr / period) + tr_list[idx]
            sm_plus = sm_plus - (sm_plus / period) + plus_dm_list[idx]
            sm_minus = sm_minus - (sm_minus / period) + minus_dm_list[idx]
        if sm_tr <= 1e-12:
            dx_values.append(0.0)
            continue
        plus_di = 100.0 * (sm_plus / sm_tr)
        minus_di = 100.0 * (sm_minus / sm_tr)
        denom = plus_di + minus_di
        dx = 100.0 * abs(plus_di - minus_di) / denom if denom > 1e-12 else 0.0
        dx_values.append(dx)

    if len(dx_values) < period:
        return None
    adx = sum(dx_values[:period]) / period
    for d in dx_values[period:]:
        adx = (adx * (period - 1) + d) / period
    return adx


def calculate_candle_efficiency(candle: Candle) -> float:
    """Devuelve la eficiencia de cierre (0.0 a 1.0) dentro del rango total de la vela."""
    span = candle.high - candle.low
    if span <= 1e-12:
        return 0.5
    return max(0.0, min(1.0, (candle.close - candle.low) / span))


