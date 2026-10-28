import React from 'react';
import { AlertTriangle, Radio, ShieldAlert, ShieldCheck, Unplug } from 'lucide-react';
import type { DataProviderType, EngineStatusDTO } from '../../shared/types';
import { formatUtcTimestamp, getModeDescriptor } from '../utils/formatters';

interface ModeBannerProps {
  status: EngineStatusDTO;
  onToggleConnectivity: (connected: boolean) => void;
  onToggleDataProvider: (provider: DataProviderType) => void;
  onTriggerKillSwitch: () => void;
  isBusy: boolean;
}

export const ModeBanner: React.FC<ModeBannerProps> = ({
  status,
  onToggleConnectivity,
  onToggleDataProvider,
  onTriggerKillSwitch,
  isBusy,
}) => {
  const descriptor = getModeDescriptor(status.effective_mode, status.python_engine_connected);
  const isLivePublicFeed = status.data_provider === 'binance_public';

  return (
    <section
      aria-label="Estado del modo de ejecución y seguridad operativa"
      className="border-b border-slate-800 bg-[#0F172A] px-6 py-3.5"
    >
      <div className="mx-auto flex max-w-[1400px] flex-col justify-between gap-3 lg:flex-row lg:items-center">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span
            data-testid="execution-mode-indicator"
            className={`inline-flex items-center gap-1.5 font-mono text-xs font-semibold tracking-wider uppercase ${
              descriptor.code === 'LIVE'
                ? 'text-red-400'
                : descriptor.code === 'DEMO'
                  ? 'text-amber-400'
                  : 'text-emerald-400'
            }`}
          >
            {descriptor.code === 'LIVE' && <AlertTriangle className="h-4 w-4 shrink-0" />}
            {descriptor.code === 'DEMO' && <Unplug className="h-4 w-4 shrink-0" />}
            {descriptor.code === 'PAPER' && <ShieldCheck className="h-4 w-4 shrink-0" />}
            [{descriptor.code}] {descriptor.title}
          </span>
          <span aria-hidden="true" className="text-slate-600">
            ·
          </span>
          <span
            data-testid="data-provider-indicator"
            className={`inline-flex items-center gap-1.5 font-mono text-xs font-medium ${
              isLivePublicFeed ? 'text-sky-400' : 'text-slate-300'
            }`}
          >
            <Radio className="h-3.5 w-3.5 shrink-0" />
            {isLivePublicFeed
              ? 'Feed: Velas Públicas Tiempo Real (Binance Spot 1h/4h)'
              : 'Feed: Serie Determinista Reproducible (Offline)'}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <span className="font-mono text-xs text-slate-400 tabular-nums">
            Última vela cerrada: {formatUtcTimestamp(status.last_data_timestamp)}
          </span>
          <span aria-hidden="true" className="text-slate-600">
            ·
          </span>
          <button
            type="button"
            disabled={isBusy || !status.python_engine_connected}
            onClick={() =>
              onToggleDataProvider(
                isLivePublicFeed ? 'synthetic_deterministic' : 'binance_public'
              )
            }
            className={`rounded-md border px-3 py-1.5 text-xs font-semibold transition-colors whitespace-nowrap shrink-0 disabled:opacity-50 ${
              isLivePublicFeed
                ? 'border-sky-500/50 bg-sky-950/70 text-sky-200 hover:bg-sky-900/70'
                : 'border-emerald-500/40 bg-emerald-950/50 text-emerald-200 hover:bg-emerald-900/60'
            }`}
          >
            {isLivePublicFeed
              ? 'Volver a Serie Determinista Offline'
              : 'Conectar Velas Públicas en Tiempo Real (Binance)'}
          </button>

          <button
            type="button"
            disabled={isBusy}
            onClick={() => onToggleConnectivity(!status.python_engine_connected)}
            className="rounded-md border border-slate-700 bg-slate-800/80 px-3 py-1.5 text-xs font-medium text-slate-200 transition-colors hover:bg-slate-700 whitespace-nowrap shrink-0 disabled:opacity-50"
          >
            {status.python_engine_connected
              ? 'Simular Desconexión Python (DEMO)'
              : 'Reconectar Motor Python (PAPER)'}
          </button>

          {!status.kill_switch_active ? (
            <button
              type="button"
              disabled={isBusy}
              onClick={onTriggerKillSwitch}
              className="inline-flex items-center gap-1.5 rounded-md border border-red-500/40 bg-red-950/60 px-3 py-1.5 text-xs font-semibold text-red-200 transition-colors hover:bg-red-900/70 whitespace-nowrap shrink-0 disabled:opacity-50"
            >
              <ShieldAlert className="h-3.5 w-3.5 shrink-0" />
              Interruptor de Emergencia
            </button>
          ) : (
            <span className="font-mono text-xs font-semibold text-red-400 whitespace-nowrap shrink-0">
              BLOQUEO DE EMERGENCIA ACTIVO
            </span>
          )}
        </div>
      </div>
    </section>
  );
};

