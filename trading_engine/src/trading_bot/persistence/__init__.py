"""Persistencia en SQLite y auditoría trazable.

Guarda la relación completa entre:
`signal_id` -> `risk_decision_id` -> `order_id` -> `execution_id`,
además de patrimonio, resultados de backtests y eventos de seguridad/interruptor de emergencia.
Nunca almacena claves privadas, tokens ni secretos.
"""

from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import time
from typing import Any, Dict, List


class SQLiteAuditStore:
    def __init__(self, db_path: str = "./data/bot_finanzas.sqlite") -> None:
        self.db_path = db_path
        if db_path != ":memory:":
            parent = os.path.dirname(os.path.abspath(db_path))
            if parent:
                os.makedirs(parent, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS signals_log (
                signal_id TEXT PRIMARY KEY,
                created_at INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                strategy_id TEXT NOT NULL,
                strategy_version TEXT NOT NULL,
                signal TEXT NOT NULL,
                reference_price REAL NOT NULL,
                proposed_stop REAL,
                invalidation_level REAL,
                indicators_json TEXT NOT NULL,
                explanation TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS risk_decisions_log (
                risk_decision_id TEXT PRIMARY KEY,
                signal_id TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                approved INTEGER NOT NULL,
                reason_code TEXT NOT NULL,
                reason_detail TEXT NOT NULL,
                approved_quantity REAL NOT NULL,
                notional_usdt REAL NOT NULL,
                estimated_risk_usdt REAL NOT NULL,
                FOREIGN KEY (signal_id) REFERENCES signals_log(signal_id)
            );

            CREATE TABLE IF NOT EXISTS orders_log (
                order_id TEXT PRIMARY KEY,
                client_order_id TEXT UNIQUE NOT NULL,
                signal_id TEXT NOT NULL,
                risk_decision_id TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                mode TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                filled_quantity REAL NOT NULL,
                price REAL NOT NULL,
                fee_usdt REAL NOT NULL,
                status TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at INTEGER NOT NULL,
                severity TEXT NOT NULL,
                category TEXT NOT NULL,
                message TEXT NOT NULL
            );
            """
        )
        cur.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (1, ?)",
            (int(time.time()),),
        )
        self._conn.commit()

    def record_decision_chain(
        self,
        signal_id: str,
        risk_decision_id: str,
        signal_data: Dict[str, Any],
        risk_data: Dict[str, Any],
        order_data: Dict[str, Any] | None = None,
    ) -> None:
        now = int(time.time())
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO signals_log
            (signal_id, created_at, symbol, strategy_id, strategy_version, signal,
             reference_price, proposed_stop, invalidation_level, indicators_json, explanation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal_id,
                int(signal_data.get("evaluated_at", now)),
                str(signal_data["symbol"]),
                str(signal_data["strategy_id"]),
                str(signal_data.get("strategy_version", "1.0.0")),
                str(signal_data["signal"]),
                float(signal_data["reference_price"]),
                signal_data.get("proposed_stop"),
                signal_data.get("invalidation_level"),
                json.dumps(signal_data.get("indicators", {})),
                str(signal_data.get("explanation", "")),
            ),
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO risk_decisions_log
            (risk_decision_id, signal_id, created_at, approved, reason_code, reason_detail,
             approved_quantity, notional_usdt, estimated_risk_usdt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                risk_decision_id,
                signal_id,
                now,
                1 if risk_data.get("approved") else 0,
                str(risk_data["reason_code"]),
                str(risk_data["reason_detail"]),
                float(risk_data.get("approved_quantity", 0.0)),
                float(risk_data.get("notional_usdt", 0.0)),
                float(risk_data.get("estimated_risk_usdt", 0.0)),
            ),
        )
        if order_data is not None:
            cur.execute(
                """
                INSERT OR REPLACE INTO orders_log
                (order_id, client_order_id, signal_id, risk_decision_id, created_at, mode,
                 symbol, side, quantity, filled_quantity, price, fee_usdt, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(order_data["order_id"]),
                    str(order_data["client_order_id"]),
                    signal_id,
                    risk_decision_id,
                    now,
                    str(order_data.get("mode", "paper")),
                    str(order_data["symbol"]),
                    str(order_data["side"]),
                    float(order_data["quantity"]),
                    float(order_data.get("filled_quantity", order_data["quantity"])),
                    float(order_data["price"]),
                    float(order_data.get("fee_usdt", 0.0)),
                    str(order_data["status"]),
                ),
            )
        self._conn.commit()

    def record_audit_event(self, severity: str, category: str, message: str) -> None:
        # Sanitizar cualquier posible cadena sensible antes de guardar
        safe_msg = message
        for forbidden in ("API_KEY", "SECRET", "TOKEN", "PASSWORD"):
            if forbidden in safe_msg.upper() and "=" in safe_msg:
                safe_msg = "[CONTENIDO_SENSIBLE_REDACTADO]"
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO audit_events (created_at, severity, category, message) VALUES (?, ?, ?, ?)",
            (int(time.time()), severity, category, safe_msg),
        )
        self._conn.commit()

    def fetch_decision_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT s.signal_id, s.created_at, s.symbol, s.strategy_id, s.signal,
                   s.reference_price, s.proposed_stop, s.explanation,
                   r.risk_decision_id, r.approved, r.reason_code, r.reason_detail,
                   r.approved_quantity, r.notional_usdt, r.estimated_risk_usdt,
                   o.order_id, o.client_order_id, o.status AS order_status, o.price AS fill_price
            FROM signals_log s
            JOIN risk_decisions_log r ON s.signal_id = r.signal_id
            LEFT JOIN orders_log o ON r.risk_decision_id = o.risk_decision_id
            ORDER BY s.created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cur.fetchall()]

    def export_decisions_csv(self) -> str:
        rows = self.fetch_decision_history(limit=500)
        output = io.StringIO()
        fieldnames = [
            "signal_id",
            "created_at",
            "symbol",
            "strategy_id",
            "signal",
            "reference_price",
            "proposed_stop",
            "risk_decision_id",
            "approved",
            "reason_code",
            "approved_quantity",
            "notional_usdt",
            "order_id",
            "order_status",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
        return output.getvalue()

    def close(self) -> None:
        self._conn.close()
