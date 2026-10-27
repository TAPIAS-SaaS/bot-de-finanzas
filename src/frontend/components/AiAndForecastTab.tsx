import React from 'react';
import {
  Area,
  ComposedChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { AdvisorAnalysisDTO, ForecastComparisonDTO } from '../../shared/types';
import { formatUsdt, formatUtcTimestamp } from '../utils/formatters';

interface AiAndForecastTabProps {
  advisor: AdvisorAnalysisDTO | null;
  forecast: ForecastComparisonDTO | null;
  onRefreshAdvisor: () => void;
  isBusy: boolean;
}

export const AiAndForecastTab: React.FC<AiAndForecastTabProps> = ({
  advisor,
  forecast,
  onRefreshAdvisor,
  isBusy,
}) => {
  const chartData = (forecast?.statistical_baseline.point_forecast || []).map((val, idx) => ({
    step: `+${idx + 1}h`,
    p50: val,
    p10: forecast?.statistical_baseline.quantiles_p10[idx] ?? val,
    p90: forecast?.statistical_baseline.quantiles_p90[idx] ?? val,
  }));

  return (
    <div className="space-y-8">
      <div className="flex flex-col justify-between gap-4 border-b border-slate-800 pb-6 lg:flex-row lg:items-end">
        <div>
          <p className="font-mono text-xs text-slate-400">
            Ejecución protegida en servidor · Ni Gemini ni TimesFM tienen permiso para enviar órdenes o elevar límites
          </p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-100">
            Asesor Estructurado Gemini (`gemini-3.8-flash`) y Pronósticos Experimentales TimesFM
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Las salidas de IA se validan contra esquemas estrictos y actúan como insumo informativo bajo supervisión del Gestor de Riesgo.
          </p>
        </div>

        <button
          type="button"
          disabled={isBusy}
          onClick={onRefreshAdvisor}
          className="rounded-lg bg-sky-500 px-4 py-2 text-xs font-semibold text-slate-950 transition-colors hover:bg-sky-400 whitespace-nowrap shrink-0 disabled:opacity-50"
        >
          Solicitar Análisis Estructurado a Gemini
        </button>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Panel del Asesor Gemini */}
        <section
          aria-label="Informe estructurado del asesor Gemini"
          className="rounded-lg border border-slate-800 bg-[#0F172A] p-5"
        >
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div>
              <h2 className="text-base font-semibold text-slate-100">
                01. Salida Validada de `GeminiAdvisor`
              </h2>
              <p className="font-mono text-xs text-slate-400">
                Modelo: {advisor?.model_id || 'gemini-3.8-flash'} · Fuente:{' '}
                {advisor?.source === 'gemini_live_api'
                  ? 'API Gemini en Servidor'
                  : 'Modo Conservador Determinista (Fallback Seguro)'}
              </p>
            </div>
            <span className="font-mono text-xs font-bold text-sky-300">
              {advisor?.recommendation || 'HOLD'}
            </span>
          </div>

          {advisor ? (
            <div className="mt-4 space-y-4 text-xs">
              <div className="grid grid-cols-3 gap-3 rounded-md border border-slate-800 bg-[#0B101B] p-3 font-mono tabular-nums">
                <div>
                  <span className="block text-slate-400">Régimen Detectado</span>
                  <span className="mt-0.5 block font-semibold text-slate-100">
                    {advisor.market_regime}
                  </span>
                </div>
                <div>
                  <span className="block text-slate-400">Recomendación</span>
                  <span className="mt-0.5 block font-semibold text-sky-300">
                    {advisor.recommendation}
                  </span>
                </div>
                <div>
                  <span className="block text-slate-400">Confianza Heurística</span>
                  <span className="mt-0.5 block font-semibold text-slate-100">
                    {(advisor.confidence * 100).toFixed(0)}% (No calibrada)
                  </span>
                </div>
              </div>

              <div>
                <p className="font-semibold text-slate-200">Explicación del Asesor:</p>
                <p className="mt-1 leading-relaxed text-slate-300">{advisor.reason}</p>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="rounded-md border border-slate-800 bg-[#0B101B] p-3">
                  <p className="font-semibold text-emerald-400">Factores de Soporte</p>
                  <ul className="mt-1.5 space-y-1 text-slate-300">
                    {advisor.supporting_factors.map((f, i) => (
                      <li key={i}>• {f}</li>
                    ))}
                  </ul>
                </div>

                <div className="rounded-md border border-slate-800 bg-[#0B101B] p-3">
                  <p className="font-semibold text-amber-400">Factores de Riesgo y Alertas</p>
                  <ul className="mt-1.5 space-y-1 text-slate-300">
                    {advisor.risk_factors.map((f, i) => (
                      <li key={i}>• {f}</li>
                    ))}
                  </ul>
                </div>
              </div>

              <div className="rounded-md border border-slate-800/80 bg-slate-900/50 p-3 text-[11px] text-slate-400">
                <p className="font-semibold text-slate-300">Advertencias de Gobernanza IA:</p>
                {advisor.warnings.map((w, i) => (
                  <p key={i} className="mt-0.5">
                    • {w}
                  </p>
                ))}
              </div>
            </div>
          ) : (
            <p className="mt-4 text-xs text-slate-400">Cargando análisis del asesor...</p>
          )}
        </section>

        {/* Panel de Pronósticos TimesFM 2.5 vs Línea Base */}
        <section
          aria-label="Pronósticos experimentales TimesFM y línea base estadística"
          className="rounded-lg border border-slate-800 bg-[#0F172A] p-5"
        >
          <div className="border-b border-slate-800 pb-3">
            <h2 className="text-base font-semibold text-slate-100">
              02. Proveedor `ForecastProvider` (TimesFM 2.5 vs Línea Base Estadística)
            </h2>
            <p className="font-mono text-xs text-slate-400">
              Origen: {forecast ? formatUtcTimestamp(forecast.origin_timestamp) : '—'} · Horizonte: {forecast?.horizon || 12} velas (1h)
            </p>
          </div>

          {forecast && (
            <div className="mt-4 space-y-4 text-xs">
              <div className="rounded-md border border-slate-800 bg-[#0B101B] p-3">
                <div className="flex items-center justify-between font-mono">
                  <span className="text-slate-300">
                    Estado {forecast.timesfm.model_version}:
                  </span>
                  <span className="text-amber-400 font-semibold">
                    {forecast.timesfm.available
                      ? 'ACTIVO'
                      : 'DESHABILITADO / SIN CHECKPOINT LOCAL'}
                  </span>
                </div>
                <p className="mt-1.5 text-slate-400">{forecast.timesfm.error_message}</p>
              </div>

              <div>
                <div className="mb-2 flex items-center justify-between">
                  <span className="font-semibold text-slate-200">
                    Banda de Incertidumbre de Línea Base Estadística (Cuantiles P10 / P50 / P90)
                  </span>
                  <span className="font-mono text-slate-400 tabular-nums">
                    MAE base: {forecast.statistical_baseline.baseline_mae} USDT
                  </span>
                </div>

                <div className="h-56 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={chartData} margin={{ top: 8, right: 12, left: 8, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                      <XAxis dataKey="step" stroke="#64748B" tick={{ fontSize: 11 }} />
                      <YAxis
                        stroke="#64748B"
                        tick={{ fontSize: 11 }}
                        domain={['auto', 'auto']}
                        tickFormatter={(v) => `$${Math.round(v)}`}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#0B101B',
                          borderColor: '#334155',
                          fontSize: '12px',
                        }}
                        formatter={(val, name) => [
                          formatUsdt(Number(val ?? 0)),
                          String(name ?? ''),
                        ]}
                      />
                      <Area
                        type="monotone"
                        dataKey="p90"
                        name="Cuantil P90 (Techo 90%)"
                        stroke="#475569"
                        fill="#1E293B"
                        fillOpacity={0.35}
                      />
                      <Line
                        type="monotone"
                        dataKey="p50"
                        name="Pronóstico Central P50"
                        stroke="#38BDF8"
                        strokeWidth={2}
                        dot={false}
                      />
                      <Line
                        type="monotone"
                        dataKey="p10"
                        name="Cuantil P10 (Suelo 10%)"
                        stroke="#94A3B8"
                        strokeDasharray="4 4"
                        dot={false}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
};
