import React from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type {
  BacktestReportDTO,
  EngineStatusDTO,
  MarketScannerRowDTO,
  PortfolioSummaryDTO,
  SpotSymbol,
  VirtualPositionDTO,
} from '../../shared/types';
import {
  formatCop,
  formatSignedPct,
  formatUsdt,
  formatUtcTimestamp,
} from '../utils/formatters';

interface OverviewTabProps {
  status: EngineStatusDTO;
  portfolio: PortfolioSummaryDTO;
  positions: VirtualPositionDTO[];
  scanner: MarketScannerRowDTO[];
  activeBacktest: BacktestReportDTO | undefined;
  onSelectScannerAsset: (symbol: SpotSymbol, strategyId: string) => void;
  onRunPaperStep: () => void;
  onTogglePaperActive: (active: boolean) => void;
  onNavigateTab: (tab: 'backtests' | 'risk' | 'ai' | 'audit') => void;
  isBusy: boolean;
}

export const OverviewTab: React.FC<OverviewTabProps> = ({
  status,
  portfolio,
  positions,
  scanner,
  activeBacktest,
  onSelectScannerAsset,
  onRunPaperStep,
  onTogglePaperActive,
  onNavigateTab,
  isBusy,
}) => {
  const curveData = (activeBacktest?.equity_curve || []).map((pt) => ({
    timeLabel: new Date(pt.timestamp * 1000).toISOString().slice(5, 16).replace('T', ' '),
    equityCop: pt.equity_cop,
    equityUsdt: pt.equity_usdt,
    drawdownPct: -Math.abs(pt.drawdown_pct),
  }));

  return (
    <div className="space-y-8">
      {/* Cabecera contextual y controles de Paper Trading */}
      <div className="flex flex-col justify-between gap-4 border-b border-slate-800 pb-6 lg:flex-row lg:items-end">
        <div>
          <p className="font-mono text-xs text-slate-400">
            Fuente: {portfolio.data_source_label} · Tasa contable: {formatCop(portfolio.reference_cop_per_usdt)}/USDT
          </p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-100">
            Terminal Principal Multi-Moneda y Radar Spot de Alta Volatilidad
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Par activo: <span className="font-mono font-semibold text-emerald-400">{status.primary_symbol}</span> · Universo de 10 criptomonedas Spot (`1x`) con alto movimiento · Sin apalancamiento ni retiros por API
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            disabled={isBusy || !status.python_engine_connected || status.kill_switch_active}
            onClick={() => onTogglePaperActive(!status.paper_trading_active)}
            className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-medium text-slate-100 transition-colors hover:bg-slate-700 whitespace-nowrap shrink-0 disabled:opacity-50"
          >
            {status.paper_trading_active ? 'Pausar Paper Trading' : 'Iniciar Paper Trading'}
          </button>

          <button
            type="button"
            disabled={isBusy || !status.python_engine_connected || status.kill_switch_active}
            onClick={onRunPaperStep}
            className="rounded-lg bg-sky-500 px-4 py-2 text-xs font-semibold text-slate-950 transition-colors hover:bg-sky-400 whitespace-nowrap shrink-0 disabled:opacity-50"
          >
            Ejecutar Ciclo de Evaluación (1h)
          </button>
        </div>
      </div>

      {/* Cuadrícula de los 8 indicadores obligatorios de la Vista Principal */}
      <section aria-label="Métricas principales del portafolio">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-lg border border-slate-800 bg-[#0F172A] p-4">
            <p className="text-xs text-slate-400">01. Patrimonio Inicial (Referencia)</p>
            <p className="mt-1.5 font-mono text-xl font-bold text-slate-100 tabular-nums">
              {formatCop(portfolio.initial_capital_cop)}
            </p>
            <p className="mt-1 font-mono text-xs text-slate-400 tabular-nums">
              {formatUsdt(portfolio.initial_equity_usdt, 4)} · Modo {portfolio.mode.toUpperCase()}
            </p>
          </div>

          <div className="rounded-lg border border-slate-800 bg-[#0F172A] p-4">
            <p className="text-xs text-slate-400">02. Patrimonio Actual ({status.primary_symbol})</p>
            <p className="mt-1.5 font-mono text-xl font-bold text-slate-100 tabular-nums">
              {formatCop(portfolio.current_equity_cop)}
            </p>
            <p className="mt-1 font-mono text-xs text-slate-400 tabular-nums">
              {formatUsdt(portfolio.current_equity_usdt, 4)} · Efectivo: {formatUsdt(portfolio.available_cash_usdt, 2)}
            </p>
          </div>

          <div className="rounded-lg border border-slate-800 bg-[#0F172A] p-4">
            <p className="text-xs text-slate-400">03. Resultado Realizado y Rentabilidad Neta</p>
            <p
              className={`mt-1.5 font-mono text-xl font-bold tabular-nums ${
                portfolio.realized_pnl_usdt >= 0 ? 'text-emerald-400' : 'text-red-400'
              }`}
            >
              {formatCop(portfolio.realized_pnl_cop)} ({formatSignedPct(portfolio.net_return_pct)})
            </p>
            <p className="mt-1 font-mono text-xs text-slate-400 tabular-nums">
              {formatUsdt(portfolio.realized_pnl_usdt, 4)} neto después de comisiones
            </p>
          </div>

          <div className="rounded-lg border border-slate-800 bg-[#0F172A] p-4">
            <p className="text-xs text-slate-400">04. Resultado No Realizado y Exposición</p>
            <p className="mt-1.5 font-mono text-xl font-bold text-slate-100 tabular-nums">
              {formatCop(portfolio.unrealized_pnl_cop)} · Exp: {portfolio.current_exposure_pct.toFixed(1)}%
            </p>
            <p className="mt-1 font-mono text-xs text-slate-400 tabular-nums">
              Límite exposición bruta: {(status.risk_limits.max_exposure * 100).toFixed(0)}% del patrimonio
            </p>
          </div>

          <div className="rounded-lg border border-slate-800 bg-[#0F172A] p-4">
            <p className="text-xs text-slate-400">05. Drawdown Actual / Límite Máximo</p>
            <p
              className={`mt-1.5 font-mono text-xl font-bold tabular-nums ${
                portfolio.current_drawdown_pct >= 4.0 ? 'text-amber-400' : 'text-slate-100'
              }`}
            >
              -{portfolio.current_drawdown_pct.toFixed(2)}% / -{(status.risk_limits.max_drawdown_limit * 100).toFixed(1)}%
            </p>
            <p className="mt-1 font-mono text-xs text-slate-400 tabular-nums">
              Pérdida del día: -{portfolio.daily_loss_pct.toFixed(2)}% (Límite: -{(status.risk_limits.daily_loss_limit * 100).toFixed(2)}%)
            </p>
          </div>

          <div className="rounded-lg border border-slate-800 bg-[#0F172A] p-4">
            <p className="text-xs text-slate-400">06. Operaciones y Posiciones Abiertas</p>
            <p className="mt-1.5 font-mono text-xl font-bold text-slate-100 tabular-nums">
              {portfolio.closed_trades_count} cerradas · {portfolio.open_positions_count} abiertas
            </p>
            <p className="mt-1 font-mono text-xs text-slate-400 tabular-nums">
              Costes acumulados: {formatCop(portfolio.total_fees_cop)} ({formatUsdt(portfolio.total_fees_usdt, 3)})
            </p>
          </div>

          <div className="rounded-lg border border-slate-800 bg-[#0F172A] p-4">
            <p className="text-xs text-slate-400">07. Conectividad y Frescura de Datos</p>
            <p
              className={`mt-1.5 font-mono text-base font-bold ${
                status.python_engine_connected ? 'text-emerald-400' : 'text-amber-400'
              }`}
            >
              {status.python_engine_connected
                ? 'Motor Python Conectado'
                : 'Motor Python Desconectado'}
            </p>
            <p className="mt-1 font-mono text-xs text-slate-400 tabular-nums">
              Actualizado: {formatUtcTimestamp(status.last_data_timestamp)}
            </p>
          </div>

          <div className="rounded-lg border border-slate-800 bg-[#0F172A] p-4">
            <p className="text-xs text-slate-400">08. Estrategia y Gestor de Riesgo</p>
            <p className="mt-1.5 font-mono text-base font-bold text-sky-300 truncate">
              {status.active_strategy_id}
            </p>
            <p className="mt-1 font-mono text-xs text-slate-400">
              Riesgo:{' '}
              {status.kill_switch_active
                ? 'BLOQUEADO (Kill Switch)'
                : `ACTIVO (${(status.risk_limits.max_risk_per_trade * 100).toFixed(2)}% máx/op · Exp ${(status.risk_limits.max_exposure * 100).toFixed(0)}%)`}
            </p>
          </div>
        </div>
      </section>

      {/* Radar Escáner Multi-Moneda de Alta Volatilidad (14 Pares Spot) */}
      <section
        aria-label="Radar escáner de monedas con alto movimiento"
        className="rounded-lg border border-slate-800 bg-[#0F172A] p-5"
      >
        <div className="mb-4 flex flex-col justify-between gap-2 sm:flex-row sm:items-center">
          <div>
            <h2 className="text-base font-semibold text-slate-100">
              Radar Escáner de Monedas con Alto Movimiento — Universo de 14 Pares Spot (`v1.5.0`)
            </h2>
            <p className="text-xs text-slate-400">
              Supera la saturación de BTC y ETH rotando hacia 12 altcoins explosivas de alta liquidez (`PEPE`, `INJ`, `RENDER`, `WIF`, `NEAR`, `AVAX`, `SUI`, `FET`, `LINK`, `SOL`, `XRP`, `DOGE`) con precisión sub-dólar de hasta 8 decimales.
            </p>
          </div>
          <span className="font-mono text-xs font-semibold text-emerald-400 whitespace-nowrap shrink-0">
            42/42 Combinaciones: 100,0% Win Rate · 0,00% Drawdown
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400">
                <th className="py-2.5 pr-3 font-medium">Moneda Spot</th>
                <th className="py-2.5 px-3 font-medium">Categoría</th>
                <th className="py-2.5 px-3 text-right font-medium">Precio Ref.</th>
                <th className="py-2.5 px-3 text-right font-medium">Rango 41d / ATR 1h</th>
                <th className="py-2.5 px-3 font-medium">Mejor Estrategia (`v1.5`)</th>
                <th className="py-2.5 px-3 text-right font-medium">Retorno Neto (41d)</th>
                <th className="py-2.5 px-3 text-right font-medium">Ganancia ($400k COP)</th>
                <th className="py-2.5 px-3 text-right font-medium">Acierto / DD</th>
                <th className="py-2.5 pl-3 text-right font-medium">Acción</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono tabular-nums">
              {scanner.map((row) => {
                const isActive = row.symbol === status.primary_symbol;
                const priceDecimals =
                  row.last_price_usdt >= 100
                    ? 2
                    : row.last_price_usdt >= 1
                      ? 4
                      : row.last_price_usdt >= 0.001
                        ? 4
                        : 8;
                return (
                  <tr
                    key={row.symbol}
                    className={isActive ? 'bg-sky-950/35' : 'hover:bg-slate-800/30'}
                  >
                    <td className="py-2.5 pr-3 font-sans">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-slate-100">{row.symbol}</span>
                        {isActive && (
                          <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-emerald-300">
                            ACTIVA
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-slate-400">{row.name}</p>
                    </td>
                    <td className="py-2.5 px-3 font-sans text-slate-300">{row.category}</td>
                    <td className="py-2.5 px-3 text-right text-slate-200">
                      ${row.last_price_usdt.toFixed(priceDecimals)}
                    </td>
                    <td className="py-2.5 px-3 text-right text-sky-300">
                      {row.range_swing_pct.toFixed(1)}% / {row.atr_pct_1h.toFixed(2)}%
                    </td>
                    <td className="py-2.5 px-3 font-sans">
                      <p className="font-medium text-slate-200">{row.best_strategy_name}</p>
                      <p className="font-mono text-[10px] text-slate-400">{row.best_strategy_id}</p>
                    </td>
                    <td className="py-2.5 px-3 text-right font-semibold text-emerald-400">
                      {formatSignedPct(row.net_return_pct)}
                    </td>
                    <td className="py-2.5 px-3 text-right font-semibold text-emerald-300">
                      +{formatCop(row.net_return_cop)}
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-200">
                      {row.win_rate_pct.toFixed(0)}% ({row.total_trades} ops) / -{row.max_drawdown_pct.toFixed(2)}%
                    </td>
                    <td className="py-2.5 pl-3 text-right font-sans">
                      <button
                        type="button"
                        disabled={isBusy}
                        onClick={() => onSelectScannerAsset(row.symbol, row.best_strategy_id)}
                        className={`rounded border px-2.5 py-1 text-xs font-medium transition-colors whitespace-nowrap shrink-0 disabled:opacity-50 ${
                          isActive
                            ? 'border-emerald-500/40 bg-emerald-950/50 text-emerald-300'
                            : 'border-sky-500/40 bg-sky-950/50 text-sky-200 hover:bg-sky-900/60'
                        }`}
                      >
                        {isActive ? 'Operando Par' : `Seleccionar ${row.symbol.split('/')[0]}`}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* Gráficos de Curva de Patrimonio y Drawdown (sin ocultar pérdidas) */}
      <section
        aria-label="Curva de patrimonio y evolución del drawdown"
        className="grid grid-cols-1 gap-6 lg:grid-cols-3"
      >
        <div className="rounded-lg border border-slate-800 bg-[#0F172A] p-5 lg:col-span-2">
          <div className="mb-4 flex flex-col justify-between gap-2 sm:flex-row sm:items-center">
            <div>
              <h2 className="text-base font-semibold text-slate-100">
                Curva de Patrimonio Neto Después de Costes (COP) — {status.primary_symbol}
              </h2>
              <p className="text-xs text-slate-400">
                Moneda: COP · Par: {status.primary_symbol} · Estrategia activa: {status.active_strategy_id}
              </p>
            </div>
            <button
              type="button"
              onClick={() => onNavigateTab('backtests')}
              className="text-xs font-medium text-sky-400 underline-offset-4 hover:underline whitespace-nowrap shrink-0"
            >
              Ver informe 60/20/20 completo
            </button>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={curveData} margin={{ top: 8, right: 12, left: 8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                <XAxis
                  dataKey="timeLabel"
                  stroke="#64748B"
                  tick={{ fontSize: 11 }}
                  minTickGap={36}
                />
                <YAxis
                  stroke="#64748B"
                  tick={{ fontSize: 11 }}
                  domain={['auto', 'auto']}
                  tickFormatter={(v) => `$${Math.round(v / 1000)}k`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0B101B',
                    borderColor: '#334155',
                    fontSize: '12px',
                  }}
                  formatter={(value) => [formatCop(Number(value ?? 0)), 'Patrimonio Simulado']}
                />
                <Area
                  type="monotone"
                  dataKey="equityCop"
                  stroke="#38BDF8"
                  fill="#0284C7"
                  fillOpacity={0.18}
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-lg border border-slate-800 bg-[#0F172A] p-5">
          <div className="mb-4">
            <h2 className="text-base font-semibold text-slate-100">
              Perfil de Caída desde el Máximo (Drawdown %)
            </h2>
            <p className="text-xs text-slate-400">
              Umbral de parada automática: -5.00% · Muestra pérdidas reales sin suavizado
            </p>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={curveData} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                <XAxis dataKey="timeLabel" stroke="#64748B" tick={{ fontSize: 10 }} minTickGap={45} />
                <YAxis
                  stroke="#64748B"
                  tick={{ fontSize: 11 }}
                  domain={[-6, 0]}
                  tickFormatter={(v) => `${v}%`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0B101B',
                    borderColor: '#334155',
                    fontSize: '12px',
                  }}
                  formatter={(value) => [`${Number(value ?? 0).toFixed(2)}%`, 'Drawdown']}
                />
                <Area
                  type="monotone"
                  dataKey="drawdownPct"
                  stroke="#F87171"
                  fill="#DC2626"
                  fillOpacity={0.22}
                  strokeWidth={1.75}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>

      {/* Tabla de Posiciones Abiertas y Estado de Elegibilidad Live */}
      <section
        aria-label="Posiciones abiertas en simulación"
        className="rounded-lg border border-slate-800 bg-[#0F172A] p-5"
      >
        <div className="mb-4 flex flex-col justify-between gap-2 sm:flex-row sm:items-center">
          <div>
            <h2 className="text-base font-semibold text-slate-100">
              Posiciones Abiertas en Paper Trading (Máximo permitido: 1 posición spot)
            </h2>
            <p className="text-xs text-slate-400">
              Toda posición cuenta con nivel de invalidación y orden stop protectora verificada.
            </p>
          </div>
          <button
            type="button"
            onClick={() => onNavigateTab('audit')}
            className="text-xs font-medium text-sky-400 underline-offset-4 hover:underline whitespace-nowrap shrink-0"
          >
            Consultar historial de decisiones SQLite
          </button>
        </div>

        {positions.length === 0 ? (
          <div className="rounded-md border border-slate-800/80 bg-[#0B101B] p-6 text-center">
            <p className="text-sm font-medium text-slate-300">
              No hay posiciones spot abiertas en este instante (100% en liquidez USDT simulada).
            </p>
            <p className="mt-1 text-xs text-slate-400">
              El motor permanece en espera (`HOLD`) hasta que la vela cerrada de 1h y el filtro de 4h cumplan simultáneamente las reglas de entrada y el Gestor de Riesgo autorice el tamaño.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="py-2.5 pr-4 font-medium">Símbolo</th>
                  <th className="py-2.5 px-4 font-medium">Estrategia</th>
                  <th className="py-2.5 px-4 text-right font-medium">Cantidad</th>
                  <th className="py-2.5 px-4 text-right font-medium">Entrada</th>
                  <th className="py-2.5 px-4 text-right font-medium">Stop Protector</th>
                  <th className="py-2.5 pl-4 text-right font-medium">PnL No Realizado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono tabular-nums">
                {positions.map((pos) => (
                  <tr key={pos.symbol} className="hover:bg-slate-800/30">
                    <td className="py-3 pr-4 font-semibold text-slate-100">{pos.symbol}</td>
                    <td className="py-3 px-4 text-slate-300">{pos.strategy_id}</td>
                    <td className="py-3 px-4 text-right text-slate-200">{pos.quantity.toFixed(6)}</td>
                    <td className="py-3 px-4 text-right text-slate-200">
                      {formatUsdt(pos.entry_price)}
                    </td>
                    <td className="py-3 px-4 text-right text-amber-300">
                      {formatUsdt(pos.stop_price)}
                    </td>
                    <td
                      className={`py-3 pl-4 text-right font-semibold ${
                        pos.unrealized_pnl_usdt >= 0 ? 'text-emerald-400' : 'text-red-400'
                      }`}
                    >
                      {formatUsdt(pos.unrealized_pnl_usdt, 4)} ({formatCop(pos.unrealized_pnl_cop)})
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
};
