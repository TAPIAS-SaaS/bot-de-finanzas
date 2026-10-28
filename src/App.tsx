import React, { useCallback, useEffect, useState } from 'react';
import { AiAndForecastTab } from './frontend/components/AiAndForecastTab';
import { BacktestTab } from './frontend/components/BacktestTab';
import { DecisionAuditTab } from './frontend/components/DecisionAuditTab';
import { ModeBanner } from './frontend/components/ModeBanner';
import { OverviewTab } from './frontend/components/OverviewTab';
import { RiskAndLiveGateTab } from './frontend/components/RiskAndLiveGateTab';
import type {
  AdvisorAnalysisDTO,
  BacktestReportDTO,
  DataProviderType,
  DecisionAuditRowDTO,
  EngineStatusDTO,
  ForecastComparisonDTO,
  MarketScannerRowDTO,
  PortfolioSummaryDTO,
  RiskDecisionDTO,
  RiskProfileType,
  SpotSymbol,
  VirtualPositionDTO,
} from './shared/types';

type ActiveTab = 'overview' | 'backtests' | 'risk' | 'ai' | 'audit';

const ADMIN_HEADERS = {
  'Content-Type': 'application/json',
  'x-admin-token': 'dev-local-admin-token-change-in-prod',
};

export function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('overview');
  const [status, setStatus] = useState<EngineStatusDTO | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioSummaryDTO | null>(null);
  const [positions, setPositions] = useState<VirtualPositionDTO[]>([]);
  const [scanner, setScanner] = useState<MarketScannerRowDTO[]>([]);
  const [backtests, setBacktests] = useState<BacktestReportDTO[]>([]);
  const [decisions, setDecisions] = useState<DecisionAuditRowDTO[]>([]);
  const [advisor, setAdvisor] = useState<AdvisorAnalysisDTO | null>(null);
  const [forecast, setForecast] = useState<ForecastComparisonDTO | null>(null);
  const [symbol, setSymbol] = useState<SpotSymbol>('SOL/USDT');
  const [isBusy, setIsBusy] = useState<boolean>(false);
  const [bannerNotice, setBannerNotice] = useState<string | null>(null);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const loadDashboardData = useCallback(async (targetSymbol?: SpotSymbol) => {
    try {
      setErrorBanner(null);
      const qSym = targetSymbol ? `?symbol=${encodeURIComponent(targetSymbol)}` : '';
      const [statusRes, portRes, posRes, scanRes, btRes, tradesRes, fcRes, aiRes] =
        await Promise.all([
          fetch('/api/status'),
          fetch('/api/portfolio'),
          fetch('/api/positions'),
          fetch('/api/scanner'),
          fetch(`/api/backtests${qSym}`),
          fetch(`/api/trades${qSym}`),
          fetch(`/api/forecasts${qSym}`),
          fetch(`/api/ai/analysis${qSym}`),
        ]);

      if (!statusRes.ok || !portRes.ok) {
        throw new Error('Error al comunicar con el servidor backend.');
      }

      const [statusData, portData, posData, scanData, btData, tradesData, fcData, aiData] =
        await Promise.all([
          statusRes.json(),
          portRes.json(),
          posRes.json(),
          scanRes.json(),
          btRes.json(),
          tradesRes.json(),
          fcRes.json(),
          aiRes.json(),
        ]);

      setStatus(statusData);
      if (statusData?.primary_symbol) {
        setSymbol(statusData.primary_symbol);
      }
      setPortfolio(portData);
      setPositions(posData.positions || []);
      setScanner(scanData.scanner || []);
      setBacktests(btData.reports || []);
      setDecisions(tradesData.decision_history || []);
      setForecast(fcData);
      setAdvisor(aiData);
    } catch (err) {
      setErrorBanner(
        err instanceof Error
          ? err.message
          : 'Pérdida de conexión con el servidor web. Nuevas entradas bloqueadas.'
      );
    }
  }, []);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  const handleSelectSymbol = async (targetSymbol: SpotSymbol, strategyId?: string) => {
    setIsBusy(true);
    setBannerNotice(null);
    setErrorBanner(null);
    try {
      setSymbol(targetSymbol);
      const res = await fetch('/api/engine/symbol', {
        method: 'POST',
        headers: ADMIN_HEADERS,
        body: JSON.stringify({ symbol: targetSymbol, strategy_id: strategyId }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.message || 'No fue posible cambiar la moneda Spot activa.');
      }
      setStatus(data.status);
      setPortfolio(data.portfolio);
      setBacktests(data.reports || []);
      setScanner(data.scanner || []);
      await loadDashboardData(targetSymbol);
      setBannerNotice(
        `Par Spot activo cambiado a ${targetSymbol}${strategyId ? ` (${strategyId})` : ''} — Curva y métricas actualizadas.`
      );
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : 'Error al cambiar moneda Spot');
    } finally {
      setIsBusy(false);
    }
  };

  const handleRunPaperStep = async () => {
    setIsBusy(true);
    setBannerNotice(null);
    setErrorBanner(null);
    try {
      const res = await fetch('/api/paper/step', {
        method: 'POST',
        headers: ADMIN_HEADERS,
        body: JSON.stringify({ symbol }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.message || 'Ciclo de Paper Trading rechazado.');
      }
      setStatus(data.status);
      setDecisions(data.decision_history || []);
      const sig = data.step?.signal?.signal || 'HOLD';
      const rCode = data.step?.risk_decision?.reason_code || '';
      setBannerNotice(
        `Ciclo 1h evaluado en SQLite: Señal ${sig} (${symbol}) — Gestor de Riesgo: ${rCode}`
      );
      await loadDashboardData(symbol);
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : 'Error en ciclo de Paper Trading');
    } finally {
      setIsBusy(false);
    }
  };

  const handleTogglePaperActive = async (active: boolean) => {
    setIsBusy(true);
    setErrorBanner(null);
    try {
      const endpoint = active ? '/api/paper/start' : '/api/paper/pause';
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: ADMIN_HEADERS,
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.message || 'No se pudo cambiar el estado de Paper Trading');
      }
      setStatus(data);
      setBannerNotice(
        active
          ? 'Paper Trading activo en modo simulación.'
          : 'Paper Trading en pausa preventiva.'
      );
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : 'Error al actualizar Paper Trading');
    } finally {
      setIsBusy(false);
    }
  };

  const handleToggleConnectivity = async (connected: boolean) => {
    setIsBusy(true);
    setErrorBanner(null);
    try {
      const res = await fetch('/api/engine/connectivity', {
        method: 'POST',
        headers: ADMIN_HEADERS,
        body: JSON.stringify({ connected }),
      });
      const data = await res.json();
      setStatus(data);
      await loadDashboardData(symbol);
      setBannerNotice(
        connected
          ? 'Motor cuantitativo Python conectado (Modo PAPER).'
          : 'Simulación de desconexión activa: Modo DEMO (Nuevas entradas bloqueadas).'
      );
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : 'Error al cambiar conectividad');
    } finally {
      setIsBusy(false);
    }
  };

  const handleToggleDataProvider = async (provider: DataProviderType) => {
    setIsBusy(true);
    setErrorBanner(null);
    setBannerNotice(null);
    try {
      const res = await fetch('/api/engine/data-provider', {
        method: 'POST',
        headers: ADMIN_HEADERS,
        body: JSON.stringify({ provider, symbol }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.message || 'Error al cambiar el proveedor de velas');
      }
      setStatus(data.status);
      setPortfolio(data.portfolio);
      if (data.scanner) setScanner(data.scanner);
      await loadDashboardData(symbol);
      const priceLabel = data.last_signal?.reference_price
        ? ` — Último cierre ${symbol}: $${Number(data.last_signal.reference_price).toLocaleString('es-CO')} USDT`
        : '';
      setBannerNotice(
        provider === 'binance_public'
          ? `Conectado a Velas Públicas en Tiempo Real (Binance Spot REST 1h/4h sin API Key)${priceLabel}`
          : `Fuente restaurada a Serie Determinista Reproducible Offline (1.200h)${priceLabel}`
      );
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : 'Error al cambiar fuente de velas');
    } finally {
      setIsBusy(false);
    }
  };

  const handleChangeRiskProfile = async (riskProfile: RiskProfileType) => {
    setIsBusy(true);
    setErrorBanner(null);
    setBannerNotice(null);
    try {
      const res = await fetch('/api/engine/risk-profile', {
        method: 'POST',
        headers: ADMIN_HEADERS,
        body: JSON.stringify({ risk_profile: riskProfile, symbol }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.message || 'Error al cambiar el perfil de riesgo');
      }
      setStatus(data.status);
      setPortfolio(data.portfolio);
      if (data.scanner) setScanner(data.scanner);
      await loadDashboardData(symbol);
      const labels: Record<RiskProfileType, string> = {
        conservative: 'Modo Conservador (0.50% riesgo/op · 50% exposición máx)',
        balanced: 'Modo Moderado (1.25% riesgo/op · 75% exposición máx)',
        aggressive: 'Modo Arriesgado Alta Convicción v1.4 (2.00% riesgo/op · 95% exposición Spot)',
      };
      setBannerNotice(`Perfil actualizado a ${labels[riskProfile]} y backtests recalculados.`);
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : 'Error al cambiar perfil de riesgo');
    } finally {
      setIsBusy(false);
    }
  };

  const handleActivateKillSwitch = async (reason: string) => {
    setIsBusy(true);
    setErrorBanner(null);
    try {
      const res = await fetch('/api/engine/pause', {
        method: 'POST',
        headers: ADMIN_HEADERS,
        body: JSON.stringify({ reason }),
      });
      const data = await res.json();
      setStatus(data);
      setBannerNotice('Interruptor de Emergencia ACTIVADO: todas las nuevas entradas están bloqueadas.');
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : 'Error al activar Kill Switch');
    } finally {
      setIsBusy(false);
    }
  };

  const handleResumeKillSwitch = async (phrase: string) => {
    setIsBusy(true);
    setErrorBanner(null);
    try {
      const res = await fetch('/api/engine/resume', {
        method: 'POST',
        headers: ADMIN_HEADERS,
        body: JSON.stringify({ confirmation_phrase: phrase }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.message || 'Frase de confirmación inválida');
      }
      setStatus(data);
      setBannerNotice('Interruptor de Emergencia desactivado tras confirmación auditada.');
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : 'Error al reanudar motor');
    } finally {
      setIsBusy(false);
    }
  };

  const handleRunBacktests = async (
    targetSymbol: SpotSymbol,
    strategyId: string
  ) => {
    setIsBusy(true);
    setErrorBanner(null);
    try {
      setSymbol(targetSymbol);
      const res = await fetch('/api/backtests/run', {
        method: 'POST',
        headers: ADMIN_HEADERS,
        body: JSON.stringify({ symbol: targetSymbol, strategy_id: strategyId }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.message || 'Error al ejecutar backtest en motor Python.');
      }
      setBacktests(data.reports || []);
      if (data.scanner) setScanner(data.scanner);
      await loadDashboardData(targetSymbol);
      setBannerNotice(
        `Backtest reproducible 60/20/20 completado para ${targetSymbol} (${strategyId}).`
      );
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : 'Fallo en ejecución de backtest');
    } finally {
      setIsBusy(false);
    }
  };

  const handleSimulateRisk = async (params: {
    symbol: SpotSymbol;
    reference_price: number;
    proposed_stop: number;
    equity_usdt: number;
    current_exposure_usdt: number;
    daily_loss_pct: number;
    drawdown_pct: number;
  }): Promise<RiskDecisionDTO> => {
    const res = await fetch('/api/risk/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.message || 'Error en simulación de riesgo');
    }
    return data.decision;
  };

  const handleRefreshAdvisor = async () => {
    setIsBusy(true);
    try {
      const res = await fetch(
        `/api/ai/analysis?symbol=${encodeURIComponent(symbol)}&refresh=1`
      );
      const data = await res.json();
      setAdvisor(data);
      setBannerNotice('Análisis estructurado de GeminiAdvisor actualizado.');
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : 'Error al consultar GeminiAdvisor');
    } finally {
      setIsBusy(false);
    }
  };

  const activeBacktest =
    backtests.find((r) => r.strategy_id === status?.active_strategy_id) || backtests[0];

  return (
    <div className="min-h-screen bg-[#0B101B] text-slate-100 flex flex-col">
      {/* Top Bar Contract: 3 zonas separadas por gap-8 */}
      <header className="border-b border-slate-800 bg-[#0B101B] px-6 py-4">
        <div className="mx-auto flex max-w-[1400px] items-center justify-between gap-8">
          <a
            href="#top"
            onClick={(e) => {
              e.preventDefault();
              setActiveTab('overview');
            }}
            className="text-lg font-bold tracking-tight text-slate-100 whitespace-nowrap shrink-0"
          >
            Bot de Finanzas
          </a>

          <nav
            aria-label="Navegación principal del terminal"
            className="flex flex-wrap items-center gap-6 text-sm font-medium text-slate-400"
          >
            <button
              type="button"
              onClick={() => setActiveTab('overview')}
              className={`transition-colors whitespace-nowrap shrink-0 ${
                activeTab === 'overview'
                  ? 'text-sky-400 underline underline-offset-8'
                  : 'hover:text-slate-100'
              }`}
            >
              Terminal Principal
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('backtests')}
              className={`transition-colors whitespace-nowrap shrink-0 ${
                activeTab === 'backtests'
                  ? 'text-sky-400 underline underline-offset-8'
                  : 'hover:text-slate-100'
              }`}
            >
              Backtesting 60/20/20
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('risk')}
              className={`transition-colors whitespace-nowrap shrink-0 ${
                activeTab === 'risk'
                  ? 'text-sky-400 underline underline-offset-8'
                  : 'hover:text-slate-100'
              }`}
            >
              Gestor de Riesgo
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('ai')}
              className={`transition-colors whitespace-nowrap shrink-0 ${
                activeTab === 'ai'
                  ? 'text-sky-400 underline underline-offset-8'
                  : 'hover:text-slate-100'
              }`}
            >
              Gemini y TimesFM
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('audit')}
              className={`transition-colors whitespace-nowrap shrink-0 ${
                activeTab === 'audit'
                  ? 'text-sky-400 underline underline-offset-8'
                  : 'hover:text-slate-100'
              }`}
            >
              Auditoría SQLite
            </button>
          </nav>

          <div className="flex items-center shrink-0">
            <a
              href="/api/export/json"
              download="informe_completo_bot.json"
              className="rounded-lg bg-slate-800 border border-slate-700 px-4 py-2 text-xs font-medium text-slate-100 hover:bg-slate-700 transition-colors whitespace-nowrap shrink-0"
            >
              Exportar Informe JSON
            </a>
          </div>
        </div>
      </header>

      {/* Indicador superior obligatorio de Modo (DEMO / PAPER / LIVE) */}
      {status && (
        <ModeBanner
          status={status}
          onSelectSymbol={(sym) => handleSelectSymbol(sym)}
          onToggleConnectivity={handleToggleConnectivity}
          onToggleDataProvider={handleToggleDataProvider}
          onChangeRiskProfile={handleChangeRiskProfile}
          onTriggerKillSwitch={() => {
            handleActivateKillSwitch('Activación rápida desde barra superior del terminal');
          }}
          isBusy={isBusy}
        />
      )}

      {/* Notificaciones operativas o alertas de error */}
      {(bannerNotice || errorBanner) && (
        <div className="mx-auto mt-4 w-full max-w-[1400px] px-6">
          {errorBanner && (
            <div
              role="alert"
              className="rounded-md border border-red-500/40 bg-red-950/60 px-4 py-2.5 text-xs font-medium text-red-200"
            >
              Error Operativo: {errorBanner}
            </div>
          )}
          {bannerNotice && !errorBanner && (
            <div
              role="status"
              className="rounded-md border border-sky-500/30 bg-sky-950/40 px-4 py-2.5 text-xs font-medium text-sky-200"
            >
              {bannerNotice}
            </div>
          )}
        </div>
      )}

      <main className="mx-auto w-full max-w-[1400px] flex-1 px-6 py-8">
        {!status || !portfolio ? (
          <div className="rounded-lg border border-slate-800 bg-[#0F172A] p-8 text-center">
            <p className="font-mono text-sm text-slate-300">
              Inicializando motor cuantitativo y verificando integridad de SQLite...
            </p>
          </div>
        ) : (
          <>
            {activeTab === 'overview' && (
              <OverviewTab
                status={status}
                portfolio={portfolio}
                positions={positions}
                scanner={scanner}
                activeBacktest={activeBacktest}
                onSelectScannerAsset={(sym, stratId) => handleSelectSymbol(sym, stratId)}
                onRunPaperStep={handleRunPaperStep}
                onTogglePaperActive={handleTogglePaperActive}
                onNavigateTab={(t) => setActiveTab(t)}
                isBusy={isBusy}
              />
            )}

            {activeTab === 'backtests' && (
              <BacktestTab
                symbol={symbol}
                reports={backtests}
                activeStrategyId={status.active_strategy_id}
                onRunBacktests={handleRunBacktests}
                isBusy={isBusy}
              />
            )}

            {activeTab === 'risk' && (
              <RiskAndLiveGateTab
                status={status}
                onSimulateRisk={handleSimulateRisk}
                onActivateKillSwitch={handleActivateKillSwitch}
                onResumeKillSwitch={handleResumeKillSwitch}
                isBusy={isBusy}
              />
            )}

            {activeTab === 'ai' && (
              <AiAndForecastTab
                advisor={advisor}
                forecast={forecast}
                onRefreshAdvisor={handleRefreshAdvisor}
                isBusy={isBusy}
              />
            )}

            {activeTab === 'audit' && (
              <DecisionAuditTab decisions={decisions} status={status} />
            )}
          </>
        )}
      </main>

      <footer className="border-t border-slate-800/80 bg-[#0B101B] px-6 py-4 text-xs text-slate-500">
        <div className="mx-auto flex max-w-[1400px] flex-col justify-between gap-2 sm:flex-row">
          <span>
            Bot de Finanzas — Investigación cuantitativa, backtesting y paper trading spot. Sin garantías de rentabilidad futura.
          </span>
          <span className="font-mono">
            Repositorio destino: github.com/TAPIAS-SaaS/bot-de-finanzas
          </span>
        </div>
      </footer>
    </div>
  );
}

export default App;
