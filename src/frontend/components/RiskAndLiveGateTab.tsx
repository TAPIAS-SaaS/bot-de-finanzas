import React, { useState } from 'react';
import type { EngineStatusDTO, RiskDecisionDTO } from '../../shared/types';
import { formatUsdt } from '../utils/formatters';

interface RiskAndLiveGateTabProps {
  status: EngineStatusDTO;
  onSimulateRisk: (params: {
    symbol: 'BTC/USDT' | 'ETH/USDT';
    reference_price: number;
    proposed_stop: number;
    equity_usdt: number;
    current_exposure_usdt: number;
    daily_loss_pct: number;
    drawdown_pct: number;
  }) => Promise<RiskDecisionDTO>;
  onActivateKillSwitch: (reason: string) => void;
  onResumeKillSwitch: (phrase: string) => void;
  isBusy: boolean;
}

export const RiskAndLiveGateTab: React.FC<RiskAndLiveGateTabProps> = ({
  status,
  onSimulateRisk,
  onActivateKillSwitch,
  onResumeKillSwitch,
  isBusy,
}) => {
  const [simSymbol, setSimSymbol] = useState<'BTC/USDT' | 'ETH/USDT'>('BTC/USDT');
  const [refPrice, setRefPrice] = useState<string>('90000');
  const [stopPrice, setStopPrice] = useState<string>('89100');
  const [equityUsdt, setEquityUsdt] = useState<string>('95.24');
  const [dailyLossPct, setDailyLossPct] = useState<string>('0.20');
  const [drawdownPct, setDrawdownPct] = useState<string>('0.85');
  const [simResult, setSimResult] = useState<RiskDecisionDTO | null>(null);
  const [simError, setSimError] = useState<string>('');

  const [killReason, setKillReason] = useState<string>('Parada preventiva solicitada por operador');
  const [resumePhrase, setResumePhrase] = useState<string>('');

  const handleRunSimulation = async (e: React.FormEvent) => {
    e.preventDefault();
    setSimError('');
    const parsedRef = Number(refPrice);
    const parsedStop = Number(stopPrice);
    const parsedEq = Number(equityUsdt);
    const parsedDaily = Number(dailyLossPct);
    const parsedDd = Number(drawdownPct);

    if (
      !Number.isFinite(parsedRef) ||
      parsedRef <= 0 ||
      !Number.isFinite(parsedStop) ||
      parsedStop <= 0 ||
      !Number.isFinite(parsedEq) ||
      parsedEq <= 0
    ) {
      setSimError('Ingrese valores numéricos positivos válidos para precio, stop y patrimonio.');
      return;
    }

    try {
      const dec = await onSimulateRisk({
        symbol: simSymbol,
        reference_price: parsedRef,
        proposed_stop: parsedStop,
        equity_usdt: parsedEq,
        current_exposure_usdt: 0,
        daily_loss_pct: parsedDaily,
        drawdown_pct: parsedDd,
      });
      setSimResult(dec);
    } catch (err) {
      setSimError(err instanceof Error ? err.message : 'Error al evaluar en RiskManager.');
    }
  };

  return (
    <div className="space-y-8">
      <div className="border-b border-slate-800 pb-6">
        <p className="font-mono text-xs text-slate-400">
          Motor determinista independiente · Inmutable por Gemini o TimesFM
        </p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-100">
          Gestor de Riesgo (`RiskManager`), Interruptor de Emergencia y Candado Live
        </h1>
        <p className="mt-1 text-sm text-slate-400">
          Estos límites son parámetros de diseño iniciales y no constituyen una garantía contra pérdidas extremas de mercado o gaps de liquidez.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Simulador interactivo del RiskManager */}
        <section
          aria-label="Simulador determinista de tamaño de posición y rechazo"
          className="rounded-lg border border-slate-800 bg-[#0F172A] p-5"
        >
          <h2 className="text-base font-semibold text-slate-100">
            01. Verificador de Cálculo de Posición y Reglas de Rechazo
          </h2>
          <p className="mt-1 text-xs text-slate-400">
            Compruebe cómo el Gestor de Riesgo calcula el tamaño o rechaza órdenes cuando el mínimo del exchange (5.00 USDT) supera el 0,5% de riesgo permitido.
          </p>

          <form onSubmit={handleRunSimulation} className="mt-4 space-y-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className="block text-xs text-slate-300">
                <span>Símbolo Spot</span>
                <select
                  value={simSymbol}
                  onChange={(e) => setSimSymbol(e.target.value as 'BTC/USDT' | 'ETH/USDT')}
                  className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-xs text-slate-100"
                >
                  <option value="BTC/USDT">BTC/USDT</option>
                  <option value="ETH/USDT">ETH/USDT</option>
                </select>
              </label>

              <label className="block text-xs text-slate-300">
                <span>Patrimonio Actual (USDT)</span>
                <input
                  type="number"
                  step="0.01"
                  value={equityUsdt}
                  onChange={(e) => setEquityUsdt(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-xs text-slate-100"
                />
              </label>

              <label className="block text-xs text-slate-300">
                <span>Precio de Entrada Referencia (USDT)</span>
                <input
                  type="number"
                  step="0.01"
                  value={refPrice}
                  onChange={(e) => setRefPrice(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-xs text-slate-100"
                />
              </label>

              <label className="block text-xs text-slate-300">
                <span>Stop-Loss Propuesto (USDT)</span>
                <input
                  type="number"
                  step="0.01"
                  value={stopPrice}
                  onChange={(e) => setStopPrice(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-xs text-slate-100"
                />
              </label>

              <label className="block text-xs text-slate-300">
                <span>Pérdida del Día Actual (%)</span>
                <input
                  type="number"
                  step="0.05"
                  value={dailyLossPct}
                  onChange={(e) => setDailyLossPct(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-xs text-slate-100"
                />
              </label>

              <label className="block text-xs text-slate-300">
                <span>Drawdown Acumulado Actual (%)</span>
                <input
                  type="number"
                  step="0.05"
                  value={drawdownPct}
                  onChange={(e) => setDrawdownPct(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-xs text-slate-100"
                />
              </label>
            </div>

            {simError && (
              <p role="alert" className="text-xs font-medium text-red-400">
                {simError}
              </p>
            )}

            <div className="flex flex-wrap gap-2">
              <button
                type="submit"
                disabled={isBusy}
                className="rounded-lg bg-sky-500 px-4 py-2 text-xs font-semibold text-slate-950 hover:bg-sky-400 whitespace-nowrap shrink-0"
              >
                Evaluar Orden en Gestor de Riesgo
              </button>
              <button
                type="button"
                onClick={() => {
                  setRefPrice('90000');
                  setStopPrice('70000');
                }}
                className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs text-slate-200 hover:bg-slate-700 whitespace-nowrap shrink-0"
              >
                Probar Rechazo por Stop Lejano
              </button>
            </div>
          </form>

          {simResult && (
            <div
              data-testid="risk-simulation-result"
              className="mt-5 rounded-md border border-slate-800 bg-[#0B101B] p-4 text-xs"
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-200">Dictamen del RiskManager:</span>
                <span
                  className={`font-mono font-bold ${
                    simResult.approved ? 'text-emerald-400' : 'text-red-400'
                  }`}
                >
                  {simResult.approved ? 'APROBADA' : `RECHAZADA (${simResult.reason_code})`}
                </span>
              </div>
              <p className="mt-2 text-slate-300">{simResult.reason_detail}</p>
              <div className="mt-3 grid grid-cols-3 gap-2 border-t border-slate-800/80 pt-3 font-mono tabular-nums text-slate-400">
                <div>
                  <span className="block text-[11px]">Cantidad:</span>
                  <span className="text-slate-200">{simResult.approved_quantity.toFixed(6)}</span>
                </div>
                <div>
                  <span className="block text-[11px]">Valor Nocional:</span>
                  <span className="text-slate-200">{formatUsdt(simResult.notional_usdt)}</span>
                </div>
                <div>
                  <span className="block text-[11px]">Riesgo Estimado:</span>
                  <span className="text-slate-200">
                    {formatUsdt(simResult.estimated_risk_usdt)} ({(simResult.estimated_risk_pct * 100).toFixed(2)}%)
                  </span>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* Control del Interruptor de Emergencia (Kill Switch) */}
        <section
          aria-label="Interruptor de emergencia y reanudación autorizada"
          className="rounded-lg border border-slate-800 bg-[#0F172A] p-5"
        >
          <h2 className="text-base font-semibold text-slate-100">
            02. Interruptor de Emergencia (Kill Switch) y Reanudación Auditada
          </h2>
          <p className="mt-1 text-xs text-slate-400">
            Detiene inmediatamente el ciclo de nuevas decisiones e impide nuevas órdenes de entrada sin enviar órdenes opuestas a ciegas.
          </p>

          <div className="mt-4 rounded-md border border-slate-800 bg-[#0B101B] p-4">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400">Estado actual del interruptor:</span>
              <span
                data-testid="kill-switch-status"
                className={`font-mono font-bold ${
                  status.kill_switch_active ? 'text-red-400' : 'text-emerald-400'
                }`}
              >
                {status.kill_switch_active
                  ? 'ACTIVO — NUEVAS ENTRADAS BLOQUEADAS'
                  : 'NORMAL — OPERACIÓN MONITORIZADA'}
              </span>
            </div>

            {status.kill_switch_active ? (
              <div className="mt-4 space-y-3 border-t border-slate-800 pt-4">
                <p className="text-xs text-red-300">
                  Motivo registrado: {status.kill_switch_reason}
                </p>
                <label className="block text-xs text-slate-300">
                  <span>
                    Para reanudar, escriba exactamente:{' '}
                    <code className="font-mono text-sky-300">CONFIRMO_REVISION_DE_REGISTROS</code>
                  </span>
                  <input
                    type="text"
                    value={resumePhrase}
                    onChange={(e) => setResumePhrase(e.target.value)}
                    placeholder="CONFIRMO_REVISION_DE_REGISTROS"
                    className="mt-1.5 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-xs text-slate-100"
                  />
                </label>
                <button
                  type="button"
                  disabled={isBusy || resumePhrase !== 'CONFIRMO_REVISION_DE_REGISTROS'}
                  onClick={() => {
                    onResumeKillSwitch(resumePhrase);
                    setResumePhrase('');
                  }}
                  className="rounded-lg bg-emerald-500 px-4 py-2 text-xs font-semibold text-slate-950 hover:bg-emerald-400 whitespace-nowrap shrink-0 disabled:opacity-40"
                >
                  Confirmar Revisión y Desactivar Kill Switch
                </button>
              </div>
            ) : (
              <div className="mt-4 space-y-3 border-t border-slate-800 pt-4">
                <label className="block text-xs text-slate-300">
                  <span>Motivo de activación de emergencia</span>
                  <input
                    type="text"
                    value={killReason}
                    onChange={(e) => setKillReason(e.target.value)}
                    className="mt-1.5 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-100"
                  />
                </label>
                <button
                  type="button"
                  disabled={isBusy}
                  onClick={() => onActivateKillSwitch(killReason)}
                  className="rounded-lg border border-red-500/50 bg-red-950/70 px-4 py-2 text-xs font-semibold text-red-200 hover:bg-red-900/80 whitespace-nowrap shrink-0"
                >
                  Activar Interruptor de Emergencia Ahora
                </button>
              </div>
            )}
          </div>

          {/* 12 Comprobaciones obligatorias para Modo Live (Sección 13) */}
          <div className="mt-6">
            <h3 className="text-sm font-semibold text-slate-100">
              03. Estado de los 12 Controles Obligatorios para Habilitar Modo Real (LIVE)
            </h3>
            <p className="mt-0.5 text-xs text-slate-400">
              El modo real nunca puede activarse con un clic ni autoaprobarse. Requiere variables de entorno, credenciales sin retiros y aprobación fuera de muestra.
            </p>
            <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 font-mono text-xs">
              {Object.entries(status.live_readiness.checks).map(([key, passed]) => (
                <div
                  key={key}
                  className="flex items-center justify-between rounded border border-slate-800/80 bg-[#0B101B] px-3 py-2"
                >
                  <span className="truncate text-slate-300">{key}</span>
                  <span className={passed ? 'text-emerald-400 font-semibold' : 'text-amber-400'}>
                    {passed ? 'OK' : 'BLOQUEADO'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};
