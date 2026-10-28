import React, { useEffect, useState } from 'react';
import {
  SUPPORTED_SPOT_SYMBOLS,
  type BacktestReportDTO,
  type SpotSymbol,
} from '../../shared/types';
import {
  formatCop,
  formatSignedPct,
  formatUsdt,
  formatUtcTimestamp,
} from '../utils/formatters';

interface BacktestTabProps {
  symbol: SpotSymbol;
  reports: BacktestReportDTO[];
  activeStrategyId: string;
  onRunBacktests: (symbol: SpotSymbol, strategyId: string) => void;
  isBusy: boolean;
}

export const BacktestTab: React.FC<BacktestTabProps> = ({
  symbol,
  reports,
  activeStrategyId,
  onRunBacktests,
  isBusy,
}) => {
  const [selectedSymbol, setSelectedSymbol] = useState<SpotSymbol>(symbol);
  const [selectedReportId, setSelectedReportId] = useState<string>(activeStrategyId);

  useEffect(() => {
    setSelectedSymbol(symbol);
  }, [symbol]);

  useEffect(() => {
    setSelectedReportId(activeStrategyId);
  }, [activeStrategyId]);

  const detailedReport =
    reports.find((r) => r.strategy_id === selectedReportId) || reports[0];

  return (
    <div className="space-y-8">
      <div className="flex flex-col justify-between gap-4 border-b border-slate-800 pb-6 lg:flex-row lg:items-end">
        <div>
          <p className="font-mono text-xs text-slate-400">
            Partición cronológica: 60% Desarrollo · 20% Validación · 20% Prueba Fuera de Muestra (Out-of-Sample)
          </p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-100">
            Backtesting Reproducible Multi-Moneda y Comparación de Estrategias (`v1.4.0`)
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Ejecución conservadora en la apertura de la siguiente vela (sin look-ahead bias), con comisión 0.10%/lado y deslizamiento 0.05%/lado en los 10 pares Spot.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-slate-300">
            <span>Par Spot:</span>
            <select
              aria-label="Seleccionar par spot para backtesting"
              value={selectedSymbol}
              onChange={(e) => setSelectedSymbol(e.target.value as SpotSymbol)}
              className="rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 font-mono text-xs text-slate-100"
            >
              {SUPPORTED_SPOT_SYMBOLS.map((sym) => (
                <option key={sym} value={sym}>
                  {sym}
                </option>
              ))}
            </select>
          </label>

          <button
            type="button"
            disabled={isBusy}
            onClick={() => onRunBacktests(selectedSymbol, 'all')}
            className="rounded-lg bg-sky-500 px-4 py-2 text-xs font-semibold text-slate-950 transition-colors hover:bg-sky-400 whitespace-nowrap shrink-0 disabled:opacity-50"
          >
            Ejecutar Comparación 3 Estrategias ({selectedSymbol})
          </button>
        </div>
      </div>

      {/* Tabla Comparativa de las 3 Estrategias */}
      <section
        aria-label="Tabla comparativa de las tres estrategias"
        className="rounded-lg border border-slate-800 bg-[#0F172A] p-5"
      >
        <div className="mb-4">
          <h2 className="text-base font-semibold text-slate-100">
            01. Matriz Comparativa bajo Idénticos Datos, Costes y Restricciones de Riesgo
          </h2>
          <p className="text-xs text-slate-400">
            Criterios de aceptación fuera de muestra: Rentabilidad neta &gt; 0%, Profit Factor &gt; 1.10, Drawdown &le; 5.0%, Sensibilidad a +50% costes &gt; 0% y &ge; 50 operaciones.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400">
                <th className="py-2.5 pr-4 font-medium">Estrategia</th>
                <th className="py-2.5 px-3 text-right font-medium">Retorno Neto Total</th>
                <th className="py-2.5 px-3 text-right font-medium">Retorno OOS (20%)</th>
                <th className="py-2.5 px-3 text-right font-medium">Profit Factor (OOS)</th>
                <th className="py-2.5 px-3 text-right font-medium">Drawdown Máx</th>
                <th className="py-2.5 px-3 text-right font-medium">Operaciones (Tot/OOS)</th>
                <th className="py-2.5 px-3 text-right font-medium">Costes (USDT)</th>
                <th className="py-2.5 px-3 font-medium">Estado Aceptación</th>
                <th className="py-2.5 pl-3 text-right font-medium">Acción</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono tabular-nums">
              {reports.map((rep) => {
                const isSelected = rep.strategy_id === detailedReport?.strategy_id;
                return (
                  <tr
                    key={rep.strategy_id}
                    className={isSelected ? 'bg-slate-800/50' : 'hover:bg-slate-800/25'}
                  >
                    <td className="py-3 pr-4 font-sans">
                      <p className="font-semibold text-slate-100">{rep.strategy_name}</p>
                      <p className="font-mono text-[11px] text-slate-400">
                        {rep.strategy_id} · {rep.symbol}
                      </p>
                    </td>
                    <td
                      className={`py-3 px-3 text-right font-semibold ${
                        rep.overall_metrics.net_return_pct >= 0 ? 'text-emerald-400' : 'text-red-400'
                      }`}
                    >
                      {formatSignedPct(rep.overall_metrics.net_return_pct)}
                    </td>
                    <td
                      className={`py-3 px-3 text-right font-semibold ${
                        rep.out_of_sample_metrics.net_return_pct >= 0
                          ? 'text-emerald-400'
                          : 'text-red-400'
                      }`}
                    >
                      {formatSignedPct(rep.out_of_sample_metrics.net_return_pct)}
                    </td>
                    <td className="py-3 px-3 text-right text-slate-200">
                      {rep.out_of_sample_metrics.profit_factor.toFixed(2)}
                    </td>
                    <td className="py-3 px-3 text-right text-amber-300">
                      -{rep.overall_metrics.max_drawdown_pct.toFixed(2)}%
                    </td>
                    <td className="py-3 px-3 text-right text-slate-200">
                      {rep.overall_metrics.total_trades} / {rep.out_of_sample_metrics.total_trades}
                    </td>
                    <td className="py-3 px-3 text-right text-slate-300">
                      {formatUsdt(rep.overall_metrics.total_fees_usdt, 3)}
                    </td>
                    <td className="py-3 px-3 font-sans">
                      {rep.acceptance.passed ? (
                        <span className="text-emerald-400 font-medium">Aprobada en Muestra OOS</span>
                      ) : (
                        <span className="text-amber-400 font-medium">
                          Permanece en Simulación
                        </span>
                      )}
                    </td>
                    <td className="py-3 pl-3 text-right font-sans">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => setSelectedReportId(rep.strategy_id)}
                          className="rounded border border-slate-700 bg-slate-900 px-2.5 py-1 text-xs text-slate-200 hover:bg-slate-800 whitespace-nowrap shrink-0"
                        >
                          Inspeccionar
                        </button>
                        <button
                          type="button"
                          disabled={isBusy || rep.strategy_id === activeStrategyId}
                          onClick={() => onRunBacktests(selectedSymbol, rep.strategy_id)}
                          className="rounded border border-sky-500/40 bg-sky-950/50 px-2.5 py-1 text-xs text-sky-300 hover:bg-sky-900/50 whitespace-nowrap shrink-0 disabled:opacity-40"
                        >
                          {rep.strategy_id === activeStrategyId ? 'Activa (Paper)' : 'Usar en Paper'}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* Desglose por segmento (60% Desarrollo / 20% Validación / 20% Fuera de Muestra) y Diagnóstico de Aceptación */}
      {detailedReport && (
        <section
          aria-label="Desglose por muestra de la estrategia seleccionada"
          className="grid grid-cols-1 gap-6 lg:grid-cols-3"
        >
          <div className="rounded-lg border border-slate-800 bg-[#0F172A] p-5 lg:col-span-2">
            <h2 className="text-base font-semibold text-slate-100">
              02. Desglose Cronológico 60/20/20 — {detailedReport.strategy_name}
            </h2>
            <p className="mt-1 text-xs text-slate-400">
              Capital inicial: {formatCop(detailedReport.initial_capital_cop)} ({formatUsdt(detailedReport.initial_equity_usdt)}) · Capital final simulado: {formatCop(detailedReport.final_equity_cop)} ({formatUsdt(detailedReport.final_equity_usdt)})
            </p>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full border-collapse text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400">
                    <th className="py-2 pr-3 font-medium">Segmento</th>
                    <th className="py-2 px-3 text-right font-medium">Retorno Bruto</th>
                    <th className="py-2 px-3 text-right font-medium">Retorno Neto</th>
                    <th className="py-2 px-3 text-right font-medium">Buy &amp; Hold</th>
                    <th className="py-2 px-3 text-right font-medium">Acierto</th>
                    <th className="py-2 px-3 text-right font-medium">Sharpe / Sortino</th>
                    <th className="py-2 pl-3 text-right font-medium">Operaciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono tabular-nums">
                  {[
                    { label: 'Desarrollo (60%)', m: detailedReport.development_metrics },
                    { label: 'Validación (20%)', m: detailedReport.validation_metrics },
                    { label: 'Fuera de Muestra OOS (20%)', m: detailedReport.out_of_sample_metrics },
                    { label: 'Total Consolidado (100%)', m: detailedReport.overall_metrics },
                  ].map((row) => (
                    <tr key={row.label}>
                      <td className="py-2.5 pr-3 font-sans font-medium text-slate-200">
                        {row.label}
                      </td>
                      <td className="py-2.5 px-3 text-right text-slate-300">
                        {formatSignedPct(row.m.gross_return_pct)}
                      </td>
                      <td
                        className={`py-2.5 px-3 text-right font-semibold ${
                          row.m.net_return_pct >= 0 ? 'text-emerald-400' : 'text-red-400'
                        }`}
                      >
                        {formatSignedPct(row.m.net_return_pct)}
                      </td>
                      <td className="py-2.5 px-3 text-right text-slate-400">
                        {formatSignedPct(row.m.benchmark_buy_hold_pct)}
                      </td>
                      <td className="py-2.5 px-3 text-right text-slate-200">
                        {row.m.win_rate_pct.toFixed(1)}%
                      </td>
                      <td className="py-2.5 px-3 text-right text-slate-300">
                        {row.m.sharpe_ratio.toFixed(2)} / {row.m.sortino_ratio.toFixed(2)}
                      </td>
                      <td className="py-2.5 pl-3 text-right text-slate-200">
                        {row.m.total_trades}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="rounded-lg border border-slate-800 bg-[#0F172A] p-5">
            <h2 className="text-base font-semibold text-slate-100">
              03. Evaluación de Criterios Fuera de Muestra
            </h2>
            <p className="mt-1 text-xs text-slate-400">
              Si no se superan todos los umbrales, la estrategia permanece estrictamente en simulación.
            </p>

            <div className="mt-4 space-y-2.5 text-xs">
              <div className="flex justify-between border-b border-slate-800/80 pb-2">
                <span className="text-slate-400">Estado de validación OOS:</span>
                <span
                  className={`font-mono font-semibold ${
                    detailedReport.acceptance.passed ? 'text-emerald-400' : 'text-amber-400'
                  }`}
                >
                  {detailedReport.acceptance.passed ? 'APROBADO' : 'RETENIDO EN PAPER'}
                </span>
              </div>
              <div className="flex justify-between border-b border-slate-800/80 pb-2">
                <span className="text-slate-400">Operaciones OOS observadas:</span>
                <span className="font-mono text-slate-200 tabular-nums">
                  {detailedReport.acceptance.observed_oos_trades} / {detailedReport.acceptance.min_trades_required} mín.
                </span>
              </div>
              <div className="flex justify-between border-b border-slate-800/80 pb-2">
                <span className="text-slate-400">Sensibilidad a +50% costes:</span>
                <span className="font-mono text-slate-200 tabular-nums">
                  {formatSignedPct(detailedReport.acceptance.cost_stress_net_return_pct)}
                </span>
              </div>
            </div>

            <div className="mt-4 rounded-md border border-slate-800 bg-[#0B101B] p-3">
              <p className="text-xs font-semibold text-slate-200">Diagnóstico verificable:</p>
              <ul className="mt-1.5 space-y-1 text-xs text-slate-400">
                {detailedReport.acceptance.reasons.map((r, i) => (
                  <li key={i}>• {r}</li>
                ))}
              </ul>
            </div>
          </div>
        </section>
      )}

      {/* Histórico de operaciones simuladas de la estrategia seleccionada */}
      {detailedReport && (
        <section
          aria-label="Histórico de operaciones del backtest"
          className="rounded-lg border border-slate-800 bg-[#0F172A] p-5"
        >
          <h2 className="text-base font-semibold text-slate-100">
            04. Registro de Operaciones Simuladas ({detailedReport.trades.length} ejecuciones)
          </h2>
          <p className="mt-1 text-xs text-slate-400">
            Muestra las últimas 15 operaciones cerradas con precio de entrada al siguiente OPEN, salida, comisiones y motivo.
          </p>

          <div className="mt-4 overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="py-2 pr-3 font-medium">ID Operación</th>
                  <th className="py-2 px-3 font-medium">Muestra</th>
                  <th className="py-2 px-3 font-medium">Apertura (UTC)</th>
                  <th className="py-2 px-3 text-right font-medium">Precio Entrada</th>
                  <th className="py-2 px-3 text-right font-medium">Precio Salida</th>
                  <th className="py-2 px-3 text-right font-medium">Costes</th>
                  <th className="py-2 px-3 text-right font-medium">PnL Neto</th>
                  <th className="py-2 pl-3 font-medium">Motivo Salida</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono tabular-nums">
                {detailedReport.trades.slice(-15).reverse().map((tr) => {
                  const pDec =
                    tr.entry_price >= 100
                      ? 2
                      : tr.entry_price >= 1
                        ? 4
                        : tr.entry_price >= 0.001
                          ? 6
                          : 8;
                  return (
                    <tr key={tr.trade_id} className="hover:bg-slate-800/30">
                      <td className="py-2.5 pr-3 text-slate-200">{tr.trade_id}</td>
                      <td className="py-2.5 px-3 text-slate-400">{tr.segment}</td>
                      <td className="py-2.5 px-3 text-slate-300">
                        {formatUtcTimestamp(tr.entry_timestamp)}
                      </td>
                      <td className="py-2.5 px-3 text-right text-slate-200">
                        {formatUsdt(tr.entry_price, pDec)}
                      </td>
                      <td className="py-2.5 px-3 text-right text-slate-200">
                        {formatUsdt(tr.exit_price, pDec)}
                      </td>
                      <td className="py-2.5 px-3 text-right text-slate-400">
                        {formatUsdt(tr.fees_usdt, 4)}
                      </td>
                      <td
                        className={`py-2.5 px-3 text-right font-semibold ${
                          tr.net_pnl_usdt >= 0 ? 'text-emerald-400' : 'text-red-400'
                        }`}
                      >
                        {formatUsdt(tr.net_pnl_usdt, 4)} ({formatSignedPct(tr.net_return_pct)})
                      </td>
                      <td className="py-2.5 pl-3 text-slate-300">{tr.exit_reason}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
};
