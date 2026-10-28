"""Servidor API HTTP / FastAPI del motor cuantitativo Python.

Expone los endpoints autorizados del motor sin exponer métodos privilegiados
del exchange ni permitir órdenes arbitrarias desde el navegador.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict

from trading_bot.engine import TradingBotEngine


def create_engine_instance() -> TradingBotEngine:
    return TradingBotEngine()


def run_stdlib_http_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Servidor HTTP ligero de respaldo compatible con los mismos endpoints que FastAPI."""
    engine = create_engine_instance()

    class EngineRequestHandler(BaseHTTPRequestHandler):
        def _send_json(self, status_code: int, payload: Dict[str, Any]) -> None:
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._send_json(200, engine.get_status_summary()["health"])
            elif self.path == "/api/status":
                self._send_json(200, engine.get_status_summary())
            elif self.path.startswith("/api/backtests"):
                self._send_json(
                    200, {"reports": engine.run_comparative_backtest("BTC/USDT")}
                )
            else:
                self._send_json(404, {"error": "Endpoint no encontrado"})

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer((host, port), EngineRequestHandler)
    server.serve_forever()
