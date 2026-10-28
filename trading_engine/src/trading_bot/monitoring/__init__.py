"""Supervisión de salud, frescura de datos y telemetría operativa del motor."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import List


@dataclass(frozen=True)
class HealthReport:
    status: str  # 'ok' | 'degraded' | 'halted'
    engine_version: str
    trading_mode: str
    kill_switch_active: bool
    last_data_timestamp: int
    data_staleness_seconds: int
    warnings: List[str]

    def to_dict(self) -> dict:
        return asdict(self)


def build_health_report(
    trading_mode: str,
    kill_switch_active: bool,
    last_data_timestamp: int,
    max_staleness_seconds: int = 7200,
    now_utc: int | None = None,
) -> HealthReport:
    now = now_utc if now_utc is not None else int(time.time())
    staleness = max(0, now - last_data_timestamp)
    warnings: List[str] = []
    status = "ok"

    if kill_switch_active:
        status = "halted"
        warnings.append("Interruptor de emergencia (Kill Switch) activo: nuevas entradas bloqueadas.")
    elif staleness > max_staleness_seconds:
        status = "degraded"
        warnings.append(f"Datos de mercado con desfase de {staleness}s (> {max_staleness_seconds}s).")

    return HealthReport(
        status=status,
        engine_version="1.0.0",
        trading_mode=trading_mode,
        kill_switch_active=kill_switch_active,
        last_data_timestamp=last_data_timestamp,
        data_staleness_seconds=staleness,
        warnings=warnings,
    )
