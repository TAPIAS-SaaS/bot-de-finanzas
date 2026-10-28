/**
 * Persistencia SQLite en Node.js sincronizada con el esquema del motor Python (`data/bot_finanzas.sqlite`).
 * Utiliza el módulo nativo `node:sqlite` (Node 22+) sin exponer secretos ni credenciales.
 */

import fs from 'node:fs';
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import type { DecisionAuditRowDTO } from '../../src/shared/types';

export class NodeSQLiteAuditRepository {
  private db: DatabaseSync;
  public readonly dbPath: string;

  constructor(customPath?: string) {
    this.dbPath = customPath || process.env.SQLITE_DB_PATH || './data/bot_finanzas.sqlite';
    if (this.dbPath !== ':memory:') {
      const dir = path.dirname(path.resolve(this.dbPath));
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
    }
    this.db = new DatabaseSync(this.dbPath);
    this.initSchema();
  }

  private initSchema(): void {
    this.db.exec(`
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
    `);

    const countStmt = this.db.prepare('SELECT COUNT(*) as cnt FROM audit_events');
    const row = countStmt.get() as { cnt: number };
    if (row.cnt === 0) {
      this.logAuditEvent(
        'INFO',
        'BOOT',
        'Motor inicializado en modo PAPER. Operaciones reales (LIVE) bloqueadas por seguridad.'
      );
    }
  }

  public logAuditEvent(severity: 'INFO' | 'WARN' | 'CRITICAL', category: string, message: string): void {
    const sanitized = message.replace(/(API_KEY|SECRET|TOKEN|PASSWORD)\s*=\s*\S+/gi, '$1=[REDACTADO]');
    const stmt = this.db.prepare(
      'INSERT INTO audit_events (created_at, severity, category, message) VALUES (?, ?, ?, ?)'
    );
    stmt.run(Math.floor(Date.now() / 1000), severity, category, sanitized);
  }

  public getAuditEvents(limit = 30): Array<{
    event_id: number;
    created_at: number;
    severity: string;
    category: string;
    message: string;
  }> {
    const stmt = this.db.prepare(
      'SELECT event_id, created_at, severity, category, message FROM audit_events ORDER BY event_id DESC LIMIT ?'
    );
    return stmt.all(limit) as Array<{
      event_id: number;
      created_at: number;
      severity: string;
      category: string;
      message: string;
    }>;
  }

  public getDecisionHistory(limit = 50): DecisionAuditRowDTO[] {
    const stmt = this.db.prepare(`
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
    `);
    return stmt.all(limit) as unknown as DecisionAuditRowDTO[];
  }

  public exportDecisionHistoryCSV(): string {
    const rows = this.getDecisionHistory(500);
    const headers = [
      'signal_id',
      'created_at',
      'symbol',
      'strategy_id',
      'signal',
      'reference_price',
      'proposed_stop',
      'risk_decision_id',
      'approved',
      'reason_code',
      'approved_quantity',
      'notional_usdt',
      'estimated_risk_usdt',
      'order_id',
      'order_status',
      'fill_price',
    ];
    const lines = [headers.join(',')];
    for (const r of rows) {
      const vals = headers.map((h) => {
        const val = (r as unknown as Record<string, unknown>)[h];
        if (val === null || val === undefined) return '';
        const str = String(val).replace(/"/g, '""');
        return str.includes(',') ? `"${str}"` : str;
      });
      lines.push(vals.join(','));
    }
    return lines.join('\n');
  }
}
