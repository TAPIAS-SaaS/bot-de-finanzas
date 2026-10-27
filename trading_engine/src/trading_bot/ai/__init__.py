"""Asesor estructurado `GeminiAdvisor` y validador de esquema JSON.

Reglas de seguridad:
- El asesor nunca tiene acceso a ejecución de órdenes, retiros ni credenciales.
- Toda respuesta (proveniente de la API de Gemini o de un mock de prueba) se valida
  contra el esquema estricto antes de ser aceptada.
- Si la respuesta es inválida, contiene campos fuera de rango o propone una estrategia
  no incluida en `allowed_strategies`, se rechaza y se fuerza `recommendation="HOLD"`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

VALID_REGIMES = {"TRENDING", "MEAN_REVERTING", "RANGING", "VOLATILE", "UNCERTAIN"}
VALID_RECOMMENDATIONS = {"BUY", "SELL", "HOLD", "PAUSE"}


class AdvisorValidationError(ValueError):
    """Error lanzado cuando la salida del asesor IA incumple el esquema o rangos."""


@dataclass(frozen=True)
class AdvisorAnalysis:
    market_regime: str
    recommendation: str
    confidence: float
    supporting_factors: List[str]
    risk_factors: List[str]
    strategy_id: Optional[str]
    reason: str
    data_timestamp: str
    model_id: str
    warnings: List[str]

    def to_dict(self) -> dict:
        return asdict(self)


def validate_advisor_payload(
    payload: Dict[str, Any],
    allowed_strategies: List[str],
) -> AdvisorAnalysis:
    """Valida de forma estricta la estructura JSON devuelta por Gemini."""
    if not isinstance(payload, dict):
        raise AdvisorValidationError("El payload del asesor debe ser un objeto JSON.")

    required_fields = [
        "market_regime",
        "recommendation",
        "confidence",
        "supporting_factors",
        "risk_factors",
        "strategy_id",
        "reason",
        "data_timestamp",
        "model_id",
        "warnings",
    ]
    for field_name in required_fields:
        if field_name not in payload:
            raise AdvisorValidationError(f"Campo obligatorio ausente en respuesta IA: {field_name}")

    regime = str(payload["market_regime"]).strip().upper()
    if regime not in VALID_REGIMES:
        raise AdvisorValidationError(f"market_regime inválido: {regime}")

    recommendation = str(payload["recommendation"]).strip().upper()
    if recommendation not in VALID_RECOMMENDATIONS:
        raise AdvisorValidationError(f"recommendation inválida: {recommendation}")

    try:
        confidence = float(payload["confidence"])
    except (TypeError, ValueError) as exc:
        raise AdvisorValidationError("confidence debe ser un número flotante.") from exc

    if not (0.0 <= confidence <= 1.0):
        raise AdvisorValidationError(f"confidence fuera de rango [0.0, 1.0]: {confidence}")

    strategy_id = payload["strategy_id"]
    if strategy_id is not None:
        strategy_id = str(strategy_id).strip()
        if strategy_id not in allowed_strategies:
            raise AdvisorValidationError(
                f"Estrategia recomendada '{strategy_id}' no pertenece a la lista permitida."
            )

    supporting = payload["supporting_factors"]
    risks = payload["risk_factors"]
    warnings = payload["warnings"]
    if not all(isinstance(lst, list) for lst in (supporting, risks, warnings)):
        raise AdvisorValidationError("Las listas de factores y advertencias deben ser arrays JSON.")

    reason = str(payload["reason"]).strip()
    if not reason:
        raise AdvisorValidationError("El campo 'reason' no puede estar vacío.")

    return AdvisorAnalysis(
        market_regime=regime,
        recommendation=recommendation,
        confidence=round(confidence, 4),
        supporting_factors=[str(x) for x in supporting[:8]],
        risk_factors=[str(x) for x in risks[:8]],
        strategy_id=strategy_id,
        reason=reason[:1000],
        data_timestamp=str(payload["data_timestamp"]),
        model_id=str(payload["model_id"]),
        warnings=[str(x) for x in warnings[:8]],
    )


class GeminiAdvisor:
    """Asesor del motor con control de frecuencia, sanitización y fallback seguro."""

    def __init__(
        self,
        allowed_strategies: List[str],
        model_id: str = "gemini-3.8-flash",
        max_calls_per_hour: int = 15,
    ) -> None:
        self.allowed_strategies = list(allowed_strategies)
        self.model_id = model_id
        self.max_calls_per_hour = max_calls_per_hour
        self._call_timestamps: List[int] = []

    def check_rate_limit(self, current_ts: int) -> bool:
        one_hour_ago = current_ts - 3600
        self._call_timestamps = [t for t in self._call_timestamps if t > one_hour_ago]
        return len(self._call_timestamps) < self.max_calls_per_hour

    def record_call(self, current_ts: int) -> None:
        self._call_timestamps.append(current_ts)

    def parse_or_fallback(
        self,
        raw_payload: Optional[Dict[str, Any]],
        current_ts: int,
        fallback_reason: str = "Respuesta inválida o servicio Gemini no disponible",
    ) -> AdvisorAnalysis:
        if not self.check_rate_limit(current_ts):
            return self._safe_hold_fallback(
                current_ts,
                "Cuota horaria de llamadas a Gemini agotada; se mantiene HOLD por seguridad.",
            )
        if raw_payload is None:
            return self._safe_hold_fallback(current_ts, fallback_reason)
        try:
            self.record_call(current_ts)
            return validate_advisor_payload(raw_payload, self.allowed_strategies)
        except AdvisorValidationError as exc:
            return self._safe_hold_fallback(
                current_ts, f"Fallo de validación del esquema Gemini: {exc}"
            )

    def _safe_hold_fallback(self, current_ts: int, warning_msg: str) -> AdvisorAnalysis:
        return AdvisorAnalysis(
            market_regime="UNCERTAIN",
            recommendation="HOLD",
            confidence=0.0,
            supporting_factors=[],
            risk_factors=[warning_msg],
            strategy_id=None,
            reason="Modo conservador activado ante ausencia o error de validación del asesor IA.",
            data_timestamp=str(current_ts),
            model_id=self.model_id,
            warnings=[
                warning_msg,
                "La puntuación de confianza no representa una probabilidad calibrada de ganancia.",
            ],
        )
