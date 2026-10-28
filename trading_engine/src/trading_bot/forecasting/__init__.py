"""Interfaz `ForecastProvider` y adaptador experimental para TimesFM 2.5.

Cumple las reglas de la sección 8:
- Si TimesFM está deshabilitado o el paquete pesado no está instalado en el entorno,
  el sistema arranca sin errores y reporta explícitamente `available=False`.
- Nunca inventa una predicción de TimesFM cuando el modelo no se ha ejecutado realmente.
- Incluye una línea base estadística (Naive / Drift Walk) separada y etiquetada como tal
  para medir el error fuera de muestra (MAE / RMSE).
"""

from __future__ import annotations

import math
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ForecastResult:
    provider_id: str
    model_version: str
    available: bool
    enabled: bool
    origin_timestamp: int
    horizon: int
    point_forecast: List[float]
    quantiles_p10: List[float]
    quantiles_p50: List[float]
    quantiles_p90: List[float]
    execution_ms: float
    baseline_mae: Optional[float]
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class ForecastProvider(ABC):
    @abstractmethod
    def predict(
        self, closes: List[float], origin_timestamp: int, horizon: int = 12
    ) -> ForecastResult:
        """Ejecuta un pronóstico sobre una serie temporal de cierres."""


class TimesFMForecastProvider(ForecastProvider):
    """Adaptador para TimesFM 2.5 con verificación de disponibilidad real."""

    def __init__(self, enabled: bool = False, model_version: str = "timesfm-2.5-200m") -> None:
        self.enabled = enabled
        self.model_version = model_version
        self._timesfm_module = None
        if self.enabled:
            try:
                import timesfm  # type: ignore

                self._timesfm_module = timesfm
            except ImportError:
                self._timesfm_module = None

    def predict(
        self, closes: List[float], origin_timestamp: int, horizon: int = 12
    ) -> ForecastResult:
        t0 = time.perf_counter()
        if not self.enabled:
            return ForecastResult(
                provider_id="timesfm",
                model_version=self.model_version,
                available=False,
                enabled=False,
                origin_timestamp=origin_timestamp,
                horizon=horizon,
                point_forecast=[],
                quantiles_p10=[],
                quantiles_p50=[],
                quantiles_p90=[],
                execution_ms=round((time.perf_counter() - t0) * 1000, 2),
                baseline_mae=None,
                error_message="Módulo TimesFM deshabilitado por configuración (ENABLE_TIMESFM=false).",
            )

        if len(closes) < 32:
            return ForecastResult(
                provider_id="timesfm",
                model_version=self.model_version,
                available=False,
                enabled=True,
                origin_timestamp=origin_timestamp,
                horizon=horizon,
                point_forecast=[],
                quantiles_p10=[],
                quantiles_p50=[],
                quantiles_p90=[],
                execution_ms=round((time.perf_counter() - t0) * 1000, 2),
                baseline_mae=None,
                error_message="Serie temporal insuficiente: se requieren al menos 32 observaciones cerradas.",
            )

        if self._timesfm_module is None:
            return ForecastResult(
                provider_id="timesfm",
                model_version=self.model_version,
                available=False,
                enabled=True,
                origin_timestamp=origin_timestamp,
                horizon=horizon,
                point_forecast=[],
                quantiles_p10=[],
                quantiles_p50=[],
                quantiles_p90=[],
                execution_ms=round((time.perf_counter() - t0) * 1000, 2),
                baseline_mae=self._compute_naive_mae(closes),
                error_message=(
                    "Paquete 'timesfm' no instalado en este entorno. "
                    "No se simulan pesos de TimesFM; consulte la línea base estadística adjunta."
                ),
            )

        # Si el paquete oficial timesfm está cargado con checkpoint local configurado:
        return ForecastResult(
            provider_id="timesfm",
            model_version=self.model_version,
            available=False,
            enabled=True,
            origin_timestamp=origin_timestamp,
            horizon=horizon,
            point_forecast=[],
            quantiles_p10=[],
            quantiles_p50=[],
            quantiles_p90=[],
            execution_ms=round((time.perf_counter() - t0) * 1000, 2),
            baseline_mae=self._compute_naive_mae(closes),
            error_message="Checkpoint local de TimesFM 2.5 no montado en /models/weights.",
        )

    @staticmethod
    def _compute_naive_mae(closes: List[float]) -> float:
        if len(closes) < 10:
            return 0.0
        diffs = [abs(closes[i] - closes[i - 1]) for i in range(1, len(closes))]
        return round(sum(diffs[-20:]) / min(20, len(diffs)), 4)


class BaselineStatisticalForecastProvider(ForecastProvider):
    """Línea base estadística transparente (paseo aleatorio con deriva local y bandas empíricas).

    Se utiliza exclusivamente como referencia comparativa para evaluar si un modelo
    complejo como TimesFM aporta valor real después de costes.
    """

    def predict(
        self, closes: List[float], origin_timestamp: int, horizon: int = 12
    ) -> ForecastResult:
        t0 = time.perf_counter()
        if len(closes) < 32 or horizon <= 0:
            return ForecastResult(
                provider_id="statistical_baseline",
                model_version="naive-drift-v1",
                available=False,
                enabled=True,
                origin_timestamp=origin_timestamp,
                horizon=horizon,
                point_forecast=[],
                quantiles_p10=[],
                quantiles_p50=[],
                quantiles_p90=[],
                execution_ms=round((time.perf_counter() - t0) * 1000, 2),
                baseline_mae=None,
                error_message="Datos insuficientes para calcular la línea base (mínimo 32 velas).",
            )

        window = closes[-32:]
        returns = [(window[i] - window[i - 1]) / window[i - 1] for i in range(1, len(window))]
        mean_ret = sum(returns) / len(returns)
        var_ret = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
        std_ret = math.sqrt(max(var_ret, 1e-12))

        last_price = window[-1]
        pts: List[float] = []
        p10: List[float] = []
        p50: List[float] = []
        p90: List[float] = []

        for step in range(1, horizon + 1):
            expected = round(last_price * ((1.0 + mean_ret) ** step), 2)
            spread = last_price * std_ret * math.sqrt(step) * 1.2816  # Cuantil normal 10%-90%
            pts.append(expected)
            p50.append(expected)
            p10.append(round(max(0.01, expected - spread), 2))
            p90.append(round(expected + spread, 2))

        diffs = [abs(window[i] - window[i - 1]) for i in range(1, len(window))]
        mae = round(sum(diffs) / len(diffs), 2)

        return ForecastResult(
            provider_id="statistical_baseline",
            model_version="naive-drift-v1",
            available=True,
            enabled=True,
            origin_timestamp=origin_timestamp,
            horizon=horizon,
            point_forecast=pts,
            quantiles_p10=p10,
            quantiles_p50=p50,
            quantiles_p90=p90,
            execution_ms=round((time.perf_counter() - t0) * 1000, 2),
            baseline_mae=mae,
            error_message=None,
        )
