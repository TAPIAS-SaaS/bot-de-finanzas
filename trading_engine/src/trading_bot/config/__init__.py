"""Configuración central validada del motor cuantitativo.

Separa explícitamente configuración general, estrategia, riesgo, datos, Gemini,
TimesFM, exchange y ejecución. Falla de forma explícita ante valores inválidos
en lugar de sustituirlos silenciosamente.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import List

LIVE_CONFIRMATION_PHRASE = "ACEPTO_RIESGO_REAL_SPOT_SIN_GARANTIAS"


class ConfigValidationError(ValueError):
    """Error lanzado cuando la configuración incumple las reglas de seguridad."""


@dataclass(frozen=True)
class GeneralConfig:
    app_env: str = "development"
    trading_mode: str = "paper"  # 'demo' | 'paper' | 'live'
    initial_capital_cop: float = 400_000.0
    reference_cop_per_usdt: float = 4_200.0
    sqlite_db_path: str = "./data/bot_finanzas.sqlite"


SUPPORTED_SPOT_SYMBOLS: List[str] = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "NEAR/USDT",
    "INJ/USDT",
    "SUI/USDT",
    "FET/USDT",
    "RENDER/USDT",
    "AVAX/USDT",
    "WIF/USDT",
    "PEPE/USDT",
    "LINK/USDT",
    "XRP/USDT",
    "DOGE/USDT",
]


@dataclass(frozen=True)
class StrategyConfig:
    active_strategy_id: str = "trend_following_v1"
    allowed_strategies: List[str] = field(
        default_factory=lambda: [
            "trend_following_v1",
            "mean_reversion_v1",
            "range_breakout_v1",
        ]
    )
    entry_timeframe: str = "1h"
    trend_timeframe: str = "4h"
    candidate_symbols: List[str] = field(
        default_factory=lambda: list(SUPPORTED_SPOT_SYMBOLS)
    )


@dataclass(frozen=True)
class RiskConfig:
    risk_profile: str = "conservative"  # 'conservative' | 'balanced' | 'aggressive'
    max_risk_per_trade: float = 0.005  # 0.5% del patrimonio (hasta 2.0% en modo aggressive)
    max_exposure: float = 0.50  # 50% del patrimonio (hasta 95% en modo aggressive spot)
    daily_loss_limit: float = 0.01  # 1.0% pérdida diaria máxima (hasta 3.0% en modo aggressive)
    max_drawdown_limit: float = 0.05  # 5.0% drawdown máximo desde el pico (hasta 10.0% en modo aggressive)
    max_concurrent_positions: int = 1
    allow_leverage: bool = False
    allow_margin: bool = False
    allow_short: bool = False
    allow_withdrawals: bool = False
    min_order_notional_usdt: float = 5.0
    default_fee_rate: float = 0.001  # 0.10% por lado
    default_slippage_rate: float = 0.0005  # 0.05% por lado
    max_data_staleness_seconds: int = 7200  # 2 horas para velas de 1h


def build_risk_config_for_profile(
    profile: str,
    default_fee_rate: float = 0.001,
    default_slippage_rate: float = 0.0005,
    min_order_notional_usdt: float = 5.0,
) -> RiskConfig:
    normalized = (profile or "conservative").strip().lower()
    if normalized == "aggressive":
        return RiskConfig(
            risk_profile="aggressive",
            max_risk_per_trade=0.020,
            max_exposure=0.95,
            daily_loss_limit=0.030,
            max_drawdown_limit=0.100,
            max_concurrent_positions=1,
            min_order_notional_usdt=min_order_notional_usdt,
            default_fee_rate=default_fee_rate,
            default_slippage_rate=default_slippage_rate,
        )
    if normalized == "balanced":
        return RiskConfig(
            risk_profile="balanced",
            max_risk_per_trade=0.0125,
            max_exposure=0.75,
            daily_loss_limit=0.020,
            max_drawdown_limit=0.080,
            max_concurrent_positions=1,
            min_order_notional_usdt=min_order_notional_usdt,
            default_fee_rate=default_fee_rate,
            default_slippage_rate=default_slippage_rate,
        )
    if normalized == "conservative":
        return RiskConfig(
            risk_profile="conservative",
            max_risk_per_trade=0.005,
            max_exposure=0.50,
            daily_loss_limit=0.010,
            max_drawdown_limit=0.050,
            max_concurrent_positions=1,
            min_order_notional_usdt=min_order_notional_usdt,
            default_fee_rate=default_fee_rate,
            default_slippage_rate=default_slippage_rate,
        )
    raise ConfigValidationError(
        f"Perfil de riesgo inválido: {profile}. Use 'conservative', 'balanced' o 'aggressive'."
    )



@dataclass(frozen=True)
class DataConfig:
    provider: str = "synthetic_deterministic"  # 'synthetic_deterministic' | 'ccxt_public'
    max_retries: int = 3
    retry_backoff_seconds: float = 1.0
    rate_limit_requests_per_minute: int = 30


@dataclass(frozen=True)
class TimesFMConfig:
    enabled: bool = False
    model_version: str = "timesfm-2.5-200m"
    horizon: int = 12
    allow_timesfm_3_auto_download: bool = False


@dataclass(frozen=True)
class GeminiConfig:
    enabled: bool = False
    model_id: str = "gemini-3.8-flash"
    max_calls_per_hour: int = 15
    timeout_seconds: float = 15.0
    mandatory_for_entry: bool = False


@dataclass(frozen=True)
class ExchangeConfig:
    exchange_id: str = "binance"
    market_type: str = "spot"
    has_api_credentials: bool = False
    account_eligibility_verified: bool = False


@dataclass(frozen=True)
class ExecutionConfig:
    allow_live_trading: bool = False
    live_trading_confirmation: str = ""
    out_of_sample_approved: bool = False
    mandatory_tests_passed: bool = False


@dataclass(frozen=True)
class BotSettings:
    general: GeneralConfig = field(default_factory=GeneralConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    data: DataConfig = field(default_factory=DataConfig)
    timesfm: TimesFMConfig = field(default_factory=TimesFMConfig)
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    exchange: ExchangeConfig = field(default_factory=ExchangeConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)

    def validate(self) -> None:
        if self.general.trading_mode not in ("demo", "paper", "live"):
            raise ConfigValidationError(
                f"Modo de trading inválido: {self.general.trading_mode}"
            )
        if self.general.initial_capital_cop <= 0:
            raise ConfigValidationError("INITIAL_CAPITAL_COP debe ser mayor que 0.")
        if self.general.reference_cop_per_usdt <= 0:
            raise ConfigValidationError("REFERENCE_COP_PER_USDT debe ser mayor que 0.")
        if not (0 < self.risk.max_risk_per_trade <= 0.02):
            raise ConfigValidationError(
                "MAX_RISK_PER_TRADE fuera de rango seguro (0, 0.02]."
            )
        if not (0 < self.risk.max_exposure <= 1.0):
            raise ConfigValidationError("MAX_EXPOSURE fuera de rango (0, 1.0].")
        if not (0 < self.risk.daily_loss_limit <= 0.05):
            raise ConfigValidationError(
                "DAILY_LOSS_LIMIT fuera de rango seguro (0, 0.05]."
            )
        if not (0 < self.risk.max_drawdown_limit <= 0.15):
            raise ConfigValidationError(
                "MAX_DRAWDOWN_LIMIT fuera de rango seguro (0, 0.15]."
            )
        if self.risk.max_concurrent_positions < 1 or self.risk.max_concurrent_positions > 3:
            raise ConfigValidationError("MAX_CONCURRENT_POSITIONS debe estar entre 1 y 3.")
        if self.risk.allow_leverage or self.risk.allow_margin or self.risk.allow_short:
            raise ConfigValidationError(
                "Apalancamiento, margen y posiciones en corto están prohibidos en v1."
            )
        if self.risk.allow_withdrawals:
            raise ConfigValidationError(
                "Los retiros mediante API están estrictamente prohibidos."
            )
        if self.exchange.market_type != "spot":
            raise ConfigValidationError("Solo se permite el mercado spot.")
        if self.timesfm.allow_timesfm_3_auto_download:
            raise ConfigValidationError(
                "Descarga automática de TimesFM 3.0 bloqueada por restricciones de licencia."
            )
        if self.strategy.active_strategy_id not in self.strategy.allowed_strategies:
            raise ConfigValidationError(
                f"Estrategia {self.strategy.active_strategy_id} no está en la lista permitida."
            )
        if self.general.trading_mode == "live":
            self._validate_live_mode()

    def _validate_live_mode(self) -> None:
        reasons: List[str] = []
        if not self.execution.allow_live_trading:
            reasons.append("ALLOW_LIVE_TRADING no está habilitado ('true').")
        if self.execution.live_trading_confirmation != LIVE_CONFIRMATION_PHRASE:
            reasons.append("LIVE_TRADING_CONFIRMATION no coincide con la frase requerida.")
        if not self.execution.mandatory_tests_passed:
            reasons.append("Las pruebas obligatorias no han sido marcadas como aprobadas.")
        if not self.execution.out_of_sample_approved:
            reasons.append("La estrategia activa no ha superado las pruebas fuera de muestra.")
        if not self.exchange.has_api_credentials:
            reasons.append("Credenciales de API del exchange ausentes.")
        if not self.exchange.account_eligibility_verified:
            reasons.append("Elegibilidad legal/KYC de la cuenta no verificada.")
        if reasons:
            raise ConfigValidationError(
                "Operaciones en modo LIVE bloqueadas: " + " ".join(reasons)
            )

    def to_public_dict(self) -> dict:
        """Devuelve la configuración sin exponer claves ni secretos."""
        return asdict(self)


def _parse_bool(val: str | None, default: bool = False) -> bool:
    if val is None or val == "":
        return default
    lowered = val.strip().lower()
    if lowered in ("true", "1", "yes"):
        return True
    if lowered in ("false", "0", "no"):
        return False
    raise ConfigValidationError(f"Valor booleano inválido: {val}")


def load_settings_from_env(env: dict | None = None) -> BotSettings:
    source = env if env is not None else os.environ
    has_creds = bool(
        source.get("EXCHANGE_API_KEY", "").strip()
        and source.get("EXCHANGE_API_SECRET", "").strip()
    )
    settings = BotSettings(
        general=GeneralConfig(
            app_env=source.get("APP_ENV", "development"),
            trading_mode=source.get("TRADING_MODE", "paper").strip().lower(),
            initial_capital_cop=float(source.get("INITIAL_CAPITAL_COP", "400000")),
            reference_cop_per_usdt=float(source.get("REFERENCE_COP_PER_USDT", "4200")),
            sqlite_db_path=source.get("SQLITE_DB_PATH", "./data/bot_finanzas.sqlite"),
        ),
        strategy=StrategyConfig(
            active_strategy_id=source.get("ACTIVE_STRATEGY_ID", "trend_following_v1"),
            entry_timeframe=source.get("ENTRY_TIMEFRAME", "1h"),
            trend_timeframe=source.get("TREND_TIMEFRAME", "4h"),
        ),
        risk=(
            build_risk_config_for_profile(
                source.get("RISK_PROFILE", "conservative"),
                default_fee_rate=float(source.get("DEFAULT_FEE_RATE", "0.001")),
                default_slippage_rate=float(source.get("DEFAULT_SLIPPAGE_RATE", "0.0005")),
                min_order_notional_usdt=float(source.get("MIN_ORDER_NOTIONAL_USDT", "5.0")),
            )
            if source.get("RISK_PROFILE")
            and not source.get("MAX_RISK_PER_TRADE")
            else RiskConfig(
                risk_profile=source.get("RISK_PROFILE", "conservative").strip().lower(),
                max_risk_per_trade=float(source.get("MAX_RISK_PER_TRADE", "0.005")),
                max_exposure=float(source.get("MAX_EXPOSURE", "0.50")),
                daily_loss_limit=float(source.get("DAILY_LOSS_LIMIT", "0.01")),
                max_drawdown_limit=float(source.get("MAX_DRAWDOWN_LIMIT", "0.05")),
                max_concurrent_positions=int(source.get("MAX_CONCURRENT_POSITIONS", "1")),
                min_order_notional_usdt=float(source.get("MIN_ORDER_NOTIONAL_USDT", "5.0")),
                default_fee_rate=float(source.get("DEFAULT_FEE_RATE", "0.001")),
                default_slippage_rate=float(source.get("DEFAULT_SLIPPAGE_RATE", "0.0005")),
            )
        ),
        data=DataConfig(
            provider=source.get("DATA_PROVIDER", "synthetic_deterministic").strip().lower(),
        ),
        timesfm=TimesFMConfig(
            enabled=_parse_bool(source.get("ENABLE_TIMESFM"), False),
            model_version=source.get("TIMESFM_MODEL_VERSION", "timesfm-2.5-200m"),
            horizon=int(source.get("TIMESFM_HORIZON", "12")),
        ),
        gemini=GeminiConfig(
            enabled=_parse_bool(source.get("ENABLE_GEMINI_ADVISOR"), False),
            model_id=source.get("GEMINI_MODEL", "gemini-3.8-flash"),
            max_calls_per_hour=int(source.get("GEMINI_MAX_CALLS_PER_HOUR", "15")),
        ),
        exchange=ExchangeConfig(
            exchange_id=source.get("EXCHANGE_ID", "binance"),
            market_type="spot",
            has_api_credentials=has_creds,
            account_eligibility_verified=_parse_bool(
                source.get("ACCOUNT_ELIGIBILITY_VERIFIED"), False
            ),
        ),
        execution=ExecutionConfig(
            allow_live_trading=_parse_bool(source.get("ALLOW_LIVE_TRADING"), False),
            live_trading_confirmation=source.get("LIVE_TRADING_CONFIRMATION", ""),
            out_of_sample_approved=_parse_bool(
                source.get("OUT_OF_SAMPLE_APPROVED"), False
            ),
            mandatory_tests_passed=_parse_bool(
                source.get("MANDATORY_TESTS_PASSED"), False
            ),
        ),
    )
    settings.validate()
    return settings
