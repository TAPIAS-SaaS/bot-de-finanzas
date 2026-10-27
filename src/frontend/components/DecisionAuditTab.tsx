import React from 'react';
import type { DecisionAuditRowDTO, EngineStatusDTO } from '../../shared/types';
import { formatUsdt, formatUtcTimestamp } from '../utils/formatters';

interface DecisionAuditTabProps {
  decisions: DecisionAuditRowDTO[];
  status: EngineStatusDTO;
}

export const DecisionAuditTab: React.FC<DecisionAuditTabProps> = ({
  decisions,
  status,
}) => {
  return (
    <div className="space-y-8">
      <div className="flex flex-col justify-between gap-4 border-b border-slate-800 pb-6 lg:flex-row lg:items-end">
        <div>
          <p className="font-mono text-xs text-slate-400">
            Persistencia SQLite auditable · Trazabilidad completa signal_id → risk_decision_id → order_id
          </p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-100">
            Historial de Decisiones, Auditoría SQLite y Sincronización con GitHub
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Cada ciclo registra la señal evaluada, los indicadores utilizados y si el Gestor de Riesgo aprobó o rechazó la operación.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <a
            href="/api/export/csv"
            download="auditoria_decisiones_bot.csv"
            className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-medium text-slate-100 transition-colors hover:bg-slate-700 whitespace-nowrap shrink-0"
          >
            Descargar CSV de Auditoría
          </a>
          <a
            href="/api/export/json"
            download="informe_completo_bot.json"
            className="rounded-lg bg-sky-500 px-4 py-2 text-xs font-semibold text-slate-950 transition-colors hover:bg-sky-400 whitespace-nowrap shrink-0"
          >
            Descargar Informe Completo JSON
          </a>
        </div>
      </div>

      {/* Tabla de Historial de Decisiones */}
      <section
        aria-label="Tabla de trazabilidad de decisiones en SQLite"
        className="rounded-lg border border-slate-800 bg-[#0F172A] p-5"
      >
        <h2 className="text-base font-semibold text-slate-100">
          01. Trazabilidad de Señales y Decisiones del Gestor de Riesgo ({decisions.length} registros)
        </h2>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400">
                <th className="py-2.5 pr-3 font-medium">ID Señal / Fecha UTC</th>
                <th className="py-2.5 px-3 font-medium">Par / Estrategia</th>
                <th className="py-2.5 px-3 font-medium">Señal</th>
                <th className="py-2.5 px-3 text-right font-medium">Precio Ref / Stop</th>
                <th className="py-2.5 px-3 font-medium">Decisión Riesgo</th>
                <th className="py-2.5 px-3 font-medium">Orden Simulada</th>
                <th className="py-2.5 pl-3 font-medium">Explicación Determinista</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono tabular-nums">
              {decisions.map((d) => (
                <tr key={d.signal_id} className="hover:bg-slate-800/30">
                  <td className="py-3 pr-3">
                    <p className="font-semibold text-slate-200">{d.signal_id}</p>
                    <p className="text-[11px] text-slate-400">{formatUtcTimestamp(d.created_at)}</p>
                  </td>
                  <td className="py-3 px-3">
                    <p className="text-slate-100">{d.symbol}</p>
                    <p className="text-[11px] text-slate-400">{d.strategy_id}</p>
                  </td>
                  <td className="py-3 px-3">
                    <span
                      className={`font-bold ${
                        d.signal === 'BUY'
                          ? 'text-emerald-400'
                          : d.signal === 'SELL'
                            ? 'text-amber-400'
                            : 'text-slate-300'
                      }`}
                    >
                      {d.signal}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-right text-slate-200">
                    <p>{formatUsdt(d.reference_price)}</p>
                    <p className="text-[11px] text-slate-400">
                      Stop: {d.proposed_stop ? formatUsdt(d.proposed_stop) : 'N/A'}
                    </p>
                  </td>
                  <td className="py-3 px-3">
                    <p className={d.approved ? 'text-emerald-400 font-semibold' : 'text-slate-300'}>
                      {d.reason_code}
                    </p>
                    <p className="font-sans text-[11px] text-slate-400">{d.reason_detail}</p>
                  </td>
                  <td className="py-3 px-3 text-slate-300">
                    {d.order_id ? `${d.order_id} (${d.order_status})` : 'Sin orden'}
                  </td>
                  <td className="py-3 pl-3 font-sans text-slate-300 max-w-xs">
                    {d.explanation}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Eventos de Seguridad y Guía de Sincronización con GitHub */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section
          aria-label="Registro de eventos de seguridad y alertas"
          className="rounded-lg border border-slate-800 bg-[#0F172A] p-5"
        >
          <h2 className="text-base font-semibold text-slate-100">
            02. Bitácora de Eventos de Seguridad y Operaciones Administrativas
          </h2>
          <div className="mt-4 space-y-2 font-mono text-xs">
            {status.audit_events.map((ev) => (
              <div
                key={ev.event_id}
                className="rounded border border-slate-800/80 bg-[#0B101B] p-3"
              >
                <div className="flex items-center justify-between text-[11px] text-slate-400">
                  <span
                    className={
                      ev.severity === 'CRITICAL'
                        ? 'text-red-400 font-bold'
                        : ev.severity === 'WARN'
                          ? 'text-amber-400 font-semibold'
                          : 'text-sky-400'
                    }
                  >
                    [{ev.severity}] {ev.category}
                  </span>
                  <span>{formatUtcTimestamp(ev.created_at)}</span>
                </div>
                <p className="mt-1 font-sans text-slate-200">{ev.message}</p>
              </div>
            ))}
          </div>
        </section>

        <section
          aria-label="Instrucciones de despliegue del motor Python y sincronización GitHub"
          className="rounded-lg border border-slate-800 bg-[#0F172A] p-5"
        >
          <h2 className="text-base font-semibold text-slate-100">
            03. Ejecución Independiente del Motor Python y Sincronización con GitHub
          </h2>
          <p className="mt-1 text-xs text-slate-400">
            Repositorio objetivo: <code className="font-mono text-sky-300">https://github.com/TAPIAS-SaaS/bot-de-finanzas.git</code>
          </p>

          <div className="mt-4 space-y-3 text-xs text-slate-300">
            <div className="rounded-md border border-slate-800 bg-[#0B101B] p-3">
              <p className="font-semibold text-slate-100">
                A. Ejecutar y probar el motor cuantitativo Python por separado:
              </p>
              <pre className="mt-2 overflow-x-auto font-mono text-[11px] text-slate-300">
{`cd trading_engine
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .
PYTHONPATH=src pytest
PYTHONPATH=src python3 -m trading_bot.cli backtest --symbol BTC/USDT`}
              </pre>
            </div>

            <div className="rounded-md border border-slate-800 bg-[#0B101B] p-3">
              <p className="font-semibold text-slate-100">
                B. Sincronizar de forma segura con GitHub (sin bases de datos ni secretos):
              </p>
              <pre className="mt-2 overflow-x-auto font-mono text-[11px] text-slate-300">
{`git init
git remote add origin https://github.com/TAPIAS-SaaS/bot-de-finanzas.git
git status --ignored  # Verificar que .env y *.sqlite están excluidos
git add .
git commit -m "feat: arquitectura inicial Bot de Finanzas (Paper/Risk/Backtest/CI)"
git push -u origin main`}
              </pre>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};
