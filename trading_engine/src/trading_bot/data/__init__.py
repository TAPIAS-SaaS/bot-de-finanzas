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


SYMBOL_BASE_PRICES: Dict[str, Tuple[float, int]] = {
    "BTC/USDT": (88_000.0, 17),
    "ETH/USDT": (3_100.0, 53),
    "SOL/USDT": (102.50, 17),
    "NEAR/USDT": (4.74, 53),
    "INJ/USDT": (8.13, 53),
    "SUI/USDT": (0.95, 17),
    "FET/USDT": (0.186, 53),
    "RENDER/USDT": (1.714, 53),
    "AVAX/USDT": (9.02, 53),
    "WIF/USDT": (0.186, 53),
    "PEPE/USDT": (0.00512, 53),
    "LINK/USDT": (11.84, 53),
    "XRP/USDT": (1.33, 17),
    "DOGE/USDT": (0.0805, 53),
}


def round_price(value: float) -> float:
    """Redondea precios dinámicamente según la magnitud del activo (BTC vs Altcoins de centavos o micro-centavos)."""
    abs_val = abs(value)
    if abs_val >= 100.0:
        return round(value, 2)
    if abs_val >= 1.0:
        return round(value, 4)
    if abs_val >= 0.001:
        return round(value, 6)
    return round(value, 8)


def generate_deterministic_market_series(
    symbol: str = "BTC/USDT",
    num_1h_bars: int = 1200,
    start_timestamp: int = 1_767_225_600,  # 2026-01-01 00:00:00 UTC (múltiplo exacto de 14400)
) -> Tuple[List[Candle], List[Candle]]:
    """Genera una serie reproducible de velas cerradas 1h y su agregación exacta 4h.

    Simula regímenes realistas de tendencia alcista, rango lateral, retroceso y ruptura
    sin depender de conexión a internet para pruebas automatizadas y backtesting reproducible.
    """
    base_price, seed_offset = SYMBOL_BASE_PRICES.get(
        symbol, (88_000.0 if symbol.startswith("BTC") else 3_100.0, 17 if symbol.startswith("BTC") else 53)
    )
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

        open_p = round_price(price)
        close_p = round_price(max(base_price * 0.4, open_p * (1.0 + drift)))
        intrabody = abs(close_p - open_p)
        wick = round_price(max(open_p * 0.0022, intrabody * 0.55))
        high_p = round_price(max(open_p, close_p) + wick)
        low_p = round_price(max(base_price * 0.05, min(open_p, close_p) - wick))

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


BINANCE_PUBLIC_ENDPOINTS = (
    "https://data-api.binance.vision/api/v3/klines",
    "https://api.binance.com/api/v3/klines",
)


def fetch_binance_public_candles(
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    limit: int = 1000,
    timeout_seconds: float = 8.0,
) -> List[Candle]:
    """Descarga velas históricas y recientes del mercado Spot público de Binance sin API Key.

    Filtra automáticamente la vela en formación (`close_time > now_utc`) marcándola
    como `is_closed=False` y devuelve la serie validada de velas cerradas.
    """
    import json
    import time
    import urllib.parse
    import urllib.request

    step = TIMEFRAME_SECONDS.get(timeframe)
    if step is None:
        raise DataIntegrityError(f"Timeframe no soportado para descarga pública: {timeframe}")

    binance_symbol = symbol.replace("/", "").upper()
    clamped_limit = max(50, min(1000, int(limit)))
    query = urllib.parse.urlencode(
        {"symbol": binance_symbol, "interval": timeframe, "limit": clamped_limit}
    )

    raw_rows = None
    last_error: Exception | None = None
    for base_url in BINANCE_PUBLIC_ENDPOINTS:
        url = f"{base_url}?{query}"
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "BotDeFinanzas-SpotQuant/1.0",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                raw_rows = json.loads(resp.read().decode("utf-8"))
                if isinstance(raw_rows, list) and len(raw_rows) > 0:
                    break
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue

    if not raw_rows or not isinstance(raw_rows, list):
        raise DataIntegrityError(
            f"No fue posible descargar velas públicas de Binance para {symbol} ({timeframe}): {last_error}"
        )

    now_sec = int(time.time())
    parsed_candles: List[Candle] = []
    for row in raw_rows:
        open_ts = int(row[0]) // 1000
        close_ts = open_ts + step
        is_closed = close_ts <= now_sec
        parsed_candles.append(
            Candle(
                timestamp=open_ts,
                close_timestamp=close_ts,
                symbol=symbol,
                timeframe=timeframe,
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[5]),
                is_closed=is_closed,
                source="binance_public_rest",
            )
        )

    return validate_candles(parsed_candles, expected_timeframe=timeframe, require_closed_only=True)


def load_market_candles_for_engine(
    symbol: str = "BTC/USDT",
    provider: str = "synthetic_deterministic",
    num_1h_bars: int = 1000,
) -> Tuple[List[Candle], List[Candle]]:
    """Carga velas cerradas 1h y 4h según el proveedor configurado (`binance_public` o `synthetic_deterministic`)."""
    normalized = provider.strip().lower()
    if normalized in ("binance_public", "ccxt_public", "live_public"):
        c1h = fetch_binance_public_candles(
            symbol=symbol,
            timeframe="1h",
            limit=min(1000, max(250, num_1h_bars)),
        )
        c4h = fetch_binance_public_candles(
            symbol=symbol,
            timeframe="4h",
            limit=min(1000, max(250, (num_1h_bars // 4) + 210)),
        )
        return c1h, c4h

    return generate_deterministic_market_series(symbol=symbol, num_1h_bars=num_1h_bars)

