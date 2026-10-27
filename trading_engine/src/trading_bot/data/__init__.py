"""Capa de datos independiente de las estrategias.

Garantiza:
- Normalización de timestamps a UTC (segundos Unix múltiplos del período).
- Detección de velas faltantes, duplicadas, desordenadas o con precios inválidos.
- Distinción explícita entre velas cerradas (`is_closed=True`) y en formación.
- Alineación multi-timeframe (1h y 4h) sin sesgo de anticipación (look-ahead bias):
  una decisión en el instante T de 1h solo puede ver velas de 4h cuyo timestamp
  de cierre sea <= T.
- Proveedor determinista de prueba sin conexión a internet.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple


class DataIntegrityError(ValueError):
    """Error lanzado cuando las series de velas presentan anomalías o datos obsoletos."""


@dataclass(frozen=True)
class Candle:
    timestamp: int  # Inicio de la vela en UTC (segundos Unix)
    close_timestamp: int  # Cierre exacto de la vela en UTC (segundos Unix)
    symbol: str
    timeframe: str  # '1h' | '4h'
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool = True
    source: str = "synthetic_deterministic"


TIMEFRAME_SECONDS: Dict[str, int] = {
    "1h": 3600,
    "4h": 14400,
}


def validate_candles(
    candles: List[Candle],
    expected_timeframe: str,
    require_closed_only: bool = True,
) -> List[Candle]:
    """Valida integridad, orden cronológico, duplicados, huecos y velas cerradas."""
    if not candles:
        raise DataIntegrityError("La lista de velas está vacía.")
    step = TIMEFRAME_SECONDS.get(expected_timeframe)
    if step is None:
        raise DataIntegrityError(f"Timeframe no soportado: {expected_timeframe}")

    filtered = [c for c in candles if c.is_closed] if require_closed_only else list(candles)
    if not filtered:
        raise DataIntegrityError("No hay velas cerradas disponibles.")

    prev_ts: int | None = None
    for idx, c in enumerate(filtered):
        if c.timeframe != expected_timeframe:
            raise DataIntegrityError(
                f"Timeframe inconsistente en índice {idx}: {c.timeframe} != {expected_timeframe}"
            )
        if any(
            math.isnan(v) or math.isinf(v) or v <= 0
            for v in (c.open, c.high, c.low, c.close)
        ) or math.isnan(c.volume) or c.volume < 0:
            raise DataIntegrityError(f"Valores numéricos inválidos en vela {c.timestamp}")
        if c.high < max(c.open, c.close) or c.low > min(c.open, c.close) or c.high < c.low:
            raise DataIntegrityError(f"Geometría OHLC incoherente en vela {c.timestamp}")
        if c.close_timestamp != c.timestamp + step:
            raise DataIntegrityError(
                f"close_timestamp inválido en vela {c.timestamp}: {c.close_timestamp}"
            )
        if prev_ts is not None:
            if c.timestamp == prev_ts:
                raise DataIntegrityError(f"Vela duplicada detectada en timestamp {c.timestamp}")
            if c.timestamp < prev_ts:
                raise DataIntegrityError(
                    f"Velas desordenadas: {c.timestamp} aparece después de {prev_ts}"
                )
            if c.timestamp - prev_ts != step:
                raise DataIntegrityError(
                    f"Vela faltante detectada entre {prev_ts} y {c.timestamp} (esperado salto de {step}s)"
                )
        prev_ts = c.timestamp

    return filtered


def align_4h_to_1h_without_lookahead(
    candles_1h: List[Candle],
    candles_4h: List[Candle],
    decision_close_ts: int,
) -> Tuple[List[Candle], List[Candle]]:
    """Devuelve únicamente las velas 1h y 4h completamente cerradas en o antes de `decision_close_ts`.

    Evita estrictamente que una decisión a las 14:00 UTC utilice la vela 4h de 12:00-16:00 UTC
    que todavía no ha cerrado.
    """
    closed_1h = [
        c for c in candles_1h if c.is_closed and c.close_timestamp <= decision_close_ts
    ]
    closed_4h = [
        c for c in candles_4h if c.is_closed and c.close_timestamp <= decision_close_ts
    ]
    return closed_1h, closed_4h


def generate_deterministic_market_series(
    symbol: str = "BTC/USDT",
    num_1h_bars: int = 1200,
    start_timestamp: int = 1_767_225_600,  # 2026-01-01 00:00:00 UTC (múltiplo exacto de 14400)
) -> Tuple[List[Candle], List[Candle]]:
    """Genera una serie reproducible de velas cerradas 1h y su agregación exacta 4h.

    Simula regímenes realistas de tendencia alcista, rango lateral, retroceso y ruptura
    sin depender de conexión a internet para pruebas automatizadas y backtesting reproducible.
    """
    base_price = 88_000.0 if symbol.startswith("BTC") else 3_100.0
    seed_offset = 17 if symbol.startswith("BTC") else 53
    step_1h = 3600
    step_4h = 14400

    aligned_start = (start_timestamp // step_4h) * step_4h
    candles_1h: List[Candle] = []
    price = base_price

    for i in range(num_1h_bars):
        ts = aligned_start + i * step_1h
        regime_phase = (i + seed_offset) % 360
        if regime_phase < 130:
            pullback = -0.0028 if (regime_phase % 18 in (12, 13, 14)) else 0.0014
            drift = pullback + 0.0032 * math.sin(i * 0.19)
        elif regime_phase < 240:
            drift = 0.0085 * math.sin(i * 0.42) - 0.0025 * math.cos(i * 0.15)
        else:
            if regime_phase < 285:
                drift = 0.0018 * math.sin(i * 0.65)
            elif regime_phase < 325:
                drift = 0.0052 + 0.0020 * math.cos(i * 0.25)
            else:
                drift = -0.0038 + 0.0015 * math.sin(i * 0.31)

        open_p = round(price, 2)
        close_p = round(max(base_price * 0.4, open_p * (1.0 + drift)), 2)
        intrabody = abs(close_p - open_p)
        wick = round(max(open_p * 0.0022, intrabody * 0.55), 2)
        high_p = round(max(open_p, close_p) + wick, 2)
        low_p = round(max(0.01, min(open_p, close_p) - wick), 2)

        vol_multiplier = 2.1 if (285 <= regime_phase < 315 or abs(drift) > 0.006) else 1.0
        volume = round(
            (140.0 + 45.0 * abs(math.sin(i * 0.37 + seed_offset))) * vol_multiplier,
            4,
        )

        candles_1h.append(
            Candle(
                timestamp=ts,
                close_timestamp=ts + step_1h,
                symbol=symbol,
                timeframe="1h",
                open=open_p,
                high=high_p,
                low=low_p,
                close=close_p,
                volume=volume,
                is_closed=True,
                source="synthetic_deterministic",
            )
        )
        price = close_p

    candles_4h: List[Candle] = []
    for j in range(0, len(candles_1h) - 3, 4):
        chunk = candles_1h[j : j + 4]
        candles_4h.append(
            Candle(
                timestamp=chunk[0].timestamp,
                close_timestamp=chunk[-1].close_timestamp,
                symbol=symbol,
                timeframe="4h",
                open=chunk[0].open,
                high=max(c.high for c in chunk),
                low=min(c.low for c in chunk),
                close=chunk[-1].close,
                volume=round(sum(c.volume for c in chunk), 4),
                is_closed=True,
                source="synthetic_deterministic",
            )
        )

    return candles_1h, candles_4h
