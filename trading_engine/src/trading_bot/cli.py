"""Interfaz de línea de comandos (`trading_bot.cli`) para ejecutar backtests, paper trading y diagnósticos."""

from __future__ import annotations

import argparse
import json
import sys

from trading_bot.api import run_stdlib_http_server
from trading_bot.backtesting import run_backtest_for_strategy
from trading_bot.config import SUPPORTED_SPOT_SYMBOLS
from trading_bot.data import load_market_candles_for_engine
from trading_bot.engine import TradingBotEngine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="trading-bot",
        description="CLI del Motor Cuantitativo Python — Bot de Finanzas",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Imprime el estado de salud y seguridad del motor en JSON")

    bt_parser = sub.add_parser("backtest", help="Ejecuta backtest reproducible 60/20/20")
    bt_parser.add_argument("--symbol", default="BTC/USDT", choices=SUPPORTED_SPOT_SYMBOLS)
    bt_parser.add_argument(
        "--strategy",
        default="all",
        choices=["all", "trend_following_v1", "mean_reversion_v1", "range_breakout_v1"],
    )
    bt_parser.add_argument(
        "--provider",
        default=None,
        choices=["synthetic_deterministic", "binance_public"],
        help="Fuente de velas: synthetic_deterministic o binance_public (tiempo real sin API key)",
    )
    bt_parser.add_argument(
        "--risk-profile",
        default=None,
        choices=["conservative", "balanced", "aggressive"],
        help="Perfil de riesgo: conservative (0.5%), balanced (1.25%) o aggressive (2.0%)",
    )

    step_parser = sub.add_parser("paper-step", help="Ejecuta un ciclo de evaluación Paper Trading")
    step_parser.add_argument("--symbol", default="BTC/USDT", choices=SUPPORTED_SPOT_SYMBOLS)
    step_parser.add_argument(
        "--provider",
        default=None,
        choices=["synthetic_deterministic", "binance_public"],
        help="Fuente de velas: synthetic_deterministic o binance_public (tiempo real sin API key)",
    )
    step_parser.add_argument(
        "--risk-profile",
        default=None,
        choices=["conservative", "balanced", "aggressive"],
        help="Perfil de riesgo: conservative (0.5%), balanced (1.25%) o aggressive (2.0%)",
    )

    serve_parser = sub.add_parser("serve", help="Inicia el servidor HTTP del motor Python")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)
    import os
    from trading_bot.config import load_settings_from_env
    env_override = dict(os.environ)
    if getattr(args, "risk_profile", None):
        env_override["RISK_PROFILE"] = args.risk_profile
        env_override.pop("MAX_RISK_PER_TRADE", None)
    engine = TradingBotEngine(settings=load_settings_from_env(env_override))

    if args.command == "status":
        print(json.dumps(engine.get_status_summary(), indent=2))
        return 0

    if args.command == "backtest":
        provider = args.provider or engine.settings.data.provider
        if args.strategy == "all":
            reports = engine.run_comparative_backtest(
                symbol=args.symbol, data_provider=provider
            )
            print(
                json.dumps(
                    {
                        "symbol": args.symbol,
                        "data_provider": provider,
                        "risk_profile": engine.settings.risk.risk_profile,
                        "reports": reports,
                    }
                )
            )
        else:
            c1h, c4h = load_market_candles_for_engine(
                symbol=args.symbol,
                provider=provider,
                num_1h_bars=1000 if provider == "binance_public" else 1200,
            )
            rep = run_backtest_for_strategy(
                strategy_id=args.strategy,
                candles_1h=c1h,
                candles_4h=c4h,
                risk_config=engine.settings.risk,
                initial_capital_cop=engine.settings.general.initial_capital_cop,
                reference_cop_per_usdt=engine.settings.general.reference_cop_per_usdt,
            )
            print(json.dumps(rep.to_dict()))
        return 0

    if args.command == "paper-step":
        res = engine.run_paper_evaluation_step(
            symbol=args.symbol, data_provider=args.provider
        )
        print(json.dumps(res))
        return 0

    if args.command == "serve":
        run_stdlib_http_server(host=args.host, port=args.port)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
