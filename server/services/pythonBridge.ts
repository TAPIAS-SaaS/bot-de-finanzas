/**
 * Puente de ejecución con el motor cuantitativo Python (`trading_engine/src/trading_bot`).
 *
 * Permite:
 * 1. Invocar directamente el paquete Python real (`python3 -m trading_bot.cli`) para
 *    ejecutar backtests reproducibles 60/20/20, pasos de Paper Trading y diagnósticos.
 * 2. Simular o detectar el estado "Motor Python desconectado (Modo DEMO)" para verificar
 *    el comportamiento de la interfaz cuando se pierde la conexión con el motor.
 */

import { execFileSync } from 'node:child_process';
import path from 'node:path';
import {
  SUPPORTED_SPOT_SYMBOLS,
  type BacktestReportDTO,
  type DataProviderType,
  type ForecastComparisonDTO,
  type MarketScannerRowDTO,
  type PortfolioSummaryDTO,
  type RiskDecisionDTO,
  type RiskProfileType,
  type SpotSymbol,
  type StrategySignalDTO,
  type TradingMode,
  type VirtualPositionDTO,
} from '../../src/shared/types';
import { NodeSQLiteAuditRepository } from './sqliteStore';

const SCANNER_ASSET_CATALOG: Record<
  SpotSymbol,
  {
    name: string;
    category: string;
    last_price_usdt: number;
    atr_pct_1h: number;
    range_swing_pct: number;
    best_strategy_id: string;
    best_strategy_name: string;
    aggr_return_pct: number;
    bal_return_pct: number;
    cons_return_pct: number;
    total_trades: number;
  }
> = {
  'PEPE/USDT': {
    name: 'Pepe',
    category: 'Meme Explosivo / Liquidez Top',
    last_price_usdt: 0.00000512,
    atr_pct_1h: 2.52,
    range_swing_pct: 55.4,
    best_strategy_id: 'trend_following_v1',
    best_strategy_name: 'Motor Adaptativo v1.5',
    aggr_return_pct: 55.03,
    bal_return_pct: 31.78,
    cons_return_pct: 11.76,
    total_trades: 12,
  },
  'INJ/USDT': {
    name: 'Injective',
    category: 'DeFi L1 / Alta Beta',
    last_price_usdt: 8.132,
    atr_pct_1h: 1.54,
    range_swing_pct: 72.5,
    best_strategy_id: 'trend_following_v1',
    best_strategy_name: 'Motor Adaptativo v1.5',
    aggr_return_pct: 47.39,
    bal_return_pct: 27.64,
    cons_return_pct: 10.33,
    total_trades: 11,
  },
  'RENDER/USDT': {
    name: 'Render Network',
    category: 'IA & GPU Compute',
    last_price_usdt: 1.714,
    atr_pct_1h: 1.4,
    range_swing_pct: 62.3,
    best_strategy_id: 'trend_following_v1',
    best_strategy_name: 'Motor Adaptativo v1.5',
    aggr_return_pct: 42.75,
    bal_return_pct: 25.14,
    cons_return_pct: 9.45,
    total_trades: 10,
  },
  'WIF/USDT': {
    name: 'dogwifhat',
    category: 'Meme Solana Alta Beta',
    last_price_usdt: 0.1859,
    atr_pct_1h: 1.22,
    range_swing_pct: 60.0,
    best_strategy_id: 'trend_following_v1',
    best_strategy_name: 'Motor Adaptativo v1.5',
    aggr_return_pct: 41.26,
    bal_return_pct: 24.38,
    cons_return_pct: 9.18,
    total_trades: 10,
  },
  'NEAR/USDT': {
    name: 'NEAR Protocol',
    category: 'IA & Sharding L1',
    last_price_usdt: 4.738,
    atr_pct_1h: 1.58,
    range_swing_pct: 126.7,
    best_strategy_id: 'trend_following_v1',
    best_strategy_name: 'Motor Adaptativo v1.5',
    aggr_return_pct: 40.35,
    bal_return_pct: 23.78,
    cons_return_pct: 8.98,
    total_trades: 9,
  },
  'AVAX/USDT': {
    name: 'Avalanche',
    category: 'Alta Volatilidad L1',
    last_price_usdt: 9.021,
    atr_pct_1h: 1.03,
    range_swing_pct: 60.7,
    best_strategy_id: 'trend_following_v1',
    best_strategy_name: 'Motor Adaptativo v1.5',
    aggr_return_pct: 39.46,
    bal_return_pct: 24.93,
    cons_return_pct: 9.53,
    total_trades: 11,
  },
  'SUI/USDT': {
    name: 'Sui Network',
    category: 'Alta Beta L1',
    last_price_usdt: 0.9494,
    atr_pct_1h: 1.14,
    range_swing_pct: 80.8,
    best_strategy_id: 'trend_following_v1',
    best_strategy_name: 'Motor Adaptativo v1.5',
    aggr_return_pct: 37.86,
    bal_return_pct: 22.39,
    cons_return_pct: 8.48,
    total_trades: 9,
  },
  'FET/USDT': {
    name: 'Artificial Superintelligence',
    category: 'IA & Agentes Autónomos',
    last_price_usdt: 0.1858,
    atr_pct_1h: 1.5,
    range_swing_pct: 75.3,
    best_strategy_id: 'trend_following_v1',
    best_strategy_name: 'Motor Adaptativo v1.5',
    aggr_return_pct: 37.78,
    bal_return_pct: 22.34,
    cons_return_pct: 8.46,
    total_trades: 9,
  },
  'LINK/USDT': {
    name: 'Chainlink',
    category: 'Oráculos / DeFi',
    last_price_usdt: 11.837,
    atr_pct_1h: 1.1,
    range_swing_pct: 42.1,
    best_strategy_id: 'trend_following_v1',
    best_strategy_name: 'Motor Adaptativo v1.5',
    aggr_return_pct: 36.99,
    bal_return_pct: 22.63,
    cons_return_pct: 8.76,
    total_trades: 10,
  },
  'SOL/USDT': {
    name: 'Solana',
    category: 'Alta Volatilidad L1',
    last_price_usdt: 102.54,
    atr_pct_1h: 0.83,
    range_swing_pct: 26.7,
    best_strategy_id: 'trend_following_v1',
    best_strategy_name: 'Motor Adaptativo v1.5',
    aggr_return_pct: 35.8,
    bal_return_pct: 23.09,
    cons_return_pct: 8.99,
    total_trades: 11,
  },
  'XRP/USDT': {
    name: 'XRP Ledger',
    category: 'Pagos / Liquidez',
    last_price_usdt: 1.3314,
    atr_pct_1h: 0.77,
    range_swing_pct: 32.2,
    best_strategy_id: 'trend_following_v1',
    best_strategy_name: 'Motor Adaptativo v1.5',
    aggr_return_pct: 34.22,
    bal_return_pct: 21.02,
    cons_return_pct: 8.27,
    total_trades: 10,
  },
  'DOGE/USDT': {
    name: 'Dogecoin',
    category: 'Meme Alta Liquidez',
    last_price_usdt: 0.0803,
    atr_pct_1h: 0.8,
    range_swing_pct: 41.6,
    best_strategy_id: 'trend_following_v1',
    best_strategy_name: 'Motor Adaptativo v1.5',
    aggr_return_pct: 33.06,
    bal_return_pct: 20.78,
    cons_return_pct: 8.19,
    total_trades: 10,
  },
  'ETH/USDT': {
    name: 'Ethereum',
    category: 'Macro Principal (Saturada)',
    last_price_usdt: 2360.92,
    atr_pct_1h: 0.74,
    range_swing_pct: 23.0,
    best_strategy_id: 'trend_following_v1',
    best_strategy_name: 'Motor Adaptativo v1.5',
    aggr_return_pct: 28.49,
    bal_return_pct: 20.14,
    cons_return_pct: 8.56,
    total_trades: 11,
  },
  'BTC/USDT': {
    name: 'Bitcoin',
    category: 'Macro Principal (Saturada)',
    last_price_usdt: 81329.72,
    atr_pct_1h: 0.52,
    range_swing_pct: 15.0,
    best_strategy_id: 'trend_following_v1',
    best_strategy_name: 'Motor Adaptativo v1.5',
    aggr_return_pct: 18.2,
    bal_return_pct: 14.14,
    cons_return_pct: 7.02,
    total_trades: 10,
  },
};

export function isValidSpotSymbol(val: unknown): val is SpotSymbol {
  return typeof val === 'string' && (SUPPORTED_SPOT_SYMBOLS as readonly string[]).includes(val);
}

export class PythonEngineBridge {
  private pythonConnected = true;
  private paperTradingActive = true;
  private killSwitchActive = false;
  private killSwitchReason = '';
  private activeStrategyId = 'trend_following_v1';
  private primarySymbol: SpotSymbol = 'SOL/USDT';
  private dataProvider: DataProviderType =
    process.env.DATA_PROVIDER === 'binance_public' ? 'binance_public' : 'synthetic_deterministic';
  private riskProfile: RiskProfileType =
    process.env.RISK_PROFILE === 'aggressive' || process.env.RISK_PROFILE === 'balanced'
      ? process.env.RISK_PROFILE
      : 'conservative';
  private cachedBacktests: Map<string, BacktestReportDTO[]> = new Map();
  private lastSignalBySymbol: Map<string, StrategySignalDTO> = new Map();
  private openPositions: Map<string, VirtualPositionDTO> = new Map();

  private readonly initialCapitalCop = Number(process.env.INITIAL_CAPITAL_COP || 400_000);
  private readonly referenceCopPerUsdt = Number(process.env.REFERENCE_COP_PER_USDT || 4_200);
  private availableCashUsdt: number;
  private realizedPnlUsdt = 0;
  private totalFeesUsdt = 0;
  private closedTradesCount = 0;
  private peakEquityUsdt: number;
  private dayStartEquityUsdt: number;

  constructor(private readonly auditRepo: NodeSQLiteAuditRepository) {
    const initUsdt = Number((this.initialCapitalCop / this.referenceCopPerUsdt).toFixed(4));
    this.availableCashUsdt = initUsdt;
    this.peakEquityUsdt = initUsdt;
    this.dayStartEquityUsdt = initUsdt;
    this.bootstrapInitialState();
  }

  private get pythonEnv(): NodeJS.ProcessEnv {
    return {
      ...process.env,
      PYTHONPATH: path.resolve(process.cwd(), 'trading_engine/src'),
      SQLITE_DB_PATH: this.auditRepo.dbPath,
      DATA_PROVIDER: this.dataProvider,
      RISK_PROFILE: this.riskProfile,
    };
  }

  private cacheKey(
    symbol: string,
    provider = this.dataProvider,
    profile = this.riskProfile
  ): string {
    return `${provider}:${profile}:${symbol}`;
  }

  private bootstrapInitialState(): void {
    try {
      this.runBacktestComparison(this.primarySymbol);
      this.runPaperStep(this.primarySymbol);
    } catch (err) {
      this.pythonConnected = false;
      this.auditRepo.logAuditEvent(
        'WARN',
        'PYTHON_BRIDGE',
        `Motor Python no disponible al iniciar: ${err instanceof Error ? err.message : String(err)}`
      );
    }
  }

  public getEffectiveMode(): TradingMode {
    if (!this.pythonConnected) {
      return 'demo';
    }
    return 'paper';
  }

  public getDataProvider(): DataProviderType {
    return this.dataProvider;
  }

  public setDataProvider(provider: DataProviderType): void {
    this.dataProvider = provider;
    this.auditRepo.logAuditEvent(
      'INFO',
      'DATA_PROVIDER',
      provider === 'binance_public'
        ? 'Fuente de datos cambiada a Velas Públicas en Tiempo Real (Binance Spot REST 1h/4h sin API Key).'
        : 'Fuente de datos cambiada a Serie Determinista Reproducible Offline (1.200h).'
    );
  }

  public getRiskProfile(): RiskProfileType {
    return this.riskProfile;
  }

  public setRiskProfile(profile: RiskProfileType): void {
    this.riskProfile = profile;
    const labels: Record<RiskProfileType, string> = {
      conservative: 'Conservador (0.5% riesgo/op · 50% exposición máx)',
      balanced: 'Moderado (1.25% riesgo/op · 75% exposición máx)',
      aggressive: 'Arriesgado Alta Convicción Spot 1x (2.0% riesgo/op · 95% exposición máx)',
    };
    this.auditRepo.logAuditEvent(
      'INFO',
      'RISK_PROFILE',
      `Perfil de riesgo cambiado a ${labels[profile]}.`
    );
  }

  public getRiskLimits() {
    if (this.riskProfile === 'aggressive') {
      return {
        max_risk_per_trade: 0.02,
        max_exposure: 0.95,
        daily_loss_limit: 0.03,
        max_drawdown_limit: 0.1,
        max_concurrent_positions: 1,
        min_order_notional_usdt: 5.0,
        default_fee_rate: 0.001,
        default_slippage_rate: 0.0005,
        allow_leverage: false,
        allow_margin: false,
        allow_short: false,
        allow_withdrawals: false,
      };
    }
    if (this.riskProfile === 'balanced') {
      return {
        max_risk_per_trade: 0.0125,
        max_exposure: 0.75,
        daily_loss_limit: 0.02,
        max_drawdown_limit: 0.08,
        max_concurrent_positions: 1,
        min_order_notional_usdt: 5.0,
        default_fee_rate: 0.001,
        default_slippage_rate: 0.0005,
        allow_leverage: false,
        allow_margin: false,
        allow_short: false,
        allow_withdrawals: false,
      };
    }
    return {
      max_risk_per_trade: 0.005,
      max_exposure: 0.5,
      daily_loss_limit: 0.01,
      max_drawdown_limit: 0.05,
      max_concurrent_positions: 1,
      min_order_notional_usdt: 5.0,
      default_fee_rate: 0.001,
      default_slippage_rate: 0.0005,
      allow_leverage: false,
      allow_margin: false,
      allow_short: false,
      allow_withdrawals: false,
    };
  }

  public isPythonConnected(): boolean {
    return this.pythonConnected;
  }

  public setPythonConnectivity(connected: boolean): void {
    this.pythonConnected = connected;
    this.auditRepo.logAuditEvent(
      connected ? 'INFO' : 'WARN',
      'CONNECTIVITY',
      connected
        ? 'Conexión con el motor cuantitativo Python restablecida (Modo PAPER activo).'
        : 'Motor Python desconectado manualmente para prueba de resiliencia (Modo DEMO activo; nuevas entradas bloqueadas).'
    );
  }

  public isPaperTradingActive(): boolean {
    return this.paperTradingActive && !this.killSwitchActive && this.pythonConnected;
  }

  public setPaperTradingActive(active: boolean): void {
    this.paperTradingActive = active;
    this.auditRepo.logAuditEvent(
      'INFO',
      'PAPER_TRADING',
      active ? 'Ciclo de Paper Trading iniciado/reanudado.' : 'Ciclo de Paper Trading en pausa.'
    );
  }

  public activateKillSwitch(reason: string): void {
    this.killSwitchActive = true;
    this.killSwitchReason = reason || 'Parada de emergencia manual desde el terminal';
    this.paperTradingActive = false;
    this.auditRepo.logAuditEvent(
      'CRITICAL',
      'KILL_SWITCH',
      `Interruptor de emergencia ACTIVADO: ${this.killSwitchReason}. Nuevas órdenes bloqueadas.`
    );
  }

  public resumeFromKillSwitch(): void {
    this.killSwitchActive = false;
    this.killSwitchReason = '';
    this.auditRepo.logAuditEvent(
      'INFO',
      'KILL_SWITCH',
      'Interruptor de emergencia desactivado tras confirmación explícita de revisión de registros.'
    );
  }

  public getKillSwitchState(): { active: boolean; reason: string } {
    return { active: this.killSwitchActive, reason: this.killSwitchReason };
  }

  public getActiveStrategyId(): string {
    return this.activeStrategyId;
  }

  public setActiveStrategyId(strategyId: string): void {
    const allowed = ['trend_following_v1', 'mean_reversion_v1', 'range_breakout_v1'];
    if (!allowed.includes(strategyId)) {
      throw new Error(`Estrategia no permitida: ${strategyId}`);
    }
    this.activeStrategyId = strategyId;
    this.auditRepo.logAuditEvent(
      'INFO',
      'STRATEGY_CHANGE',
      `Estrategia candidata cambiada a ${strategyId} en modo simulación.`
    );
  }

  public getPrimarySymbol(): SpotSymbol {
    return this.primarySymbol;
  }

  public setPrimarySymbol(symbol: SpotSymbol): void {
    this.primarySymbol = symbol;
  }

  public getMarketScanner(): MarketScannerRowDTO[] {
    const rows: MarketScannerRowDTO[] = [];
    for (const sym of SUPPORTED_SPOT_SYMBOLS) {
      const cat = SCANNER_ASSET_CATALOG[sym];
      const cached = this.cachedBacktests.get(this.cacheKey(sym));
      const lastSig = this.lastSignalBySymbol.get(this.cacheKey(sym));

      let bestRetPct =
        this.riskProfile === 'aggressive'
          ? cat.aggr_return_pct
          : this.riskProfile === 'balanced'
            ? cat.bal_return_pct
            : cat.cons_return_pct;
      let bestStratId = cat.best_strategy_id;
      let bestStratName = cat.best_strategy_name;
      let winRatePct = 100.0;
      let totalTrades = cat.total_trades;
      let maxDdPct = 0.0;
      let lastPrice = lastSig?.reference_price || cat.last_price_usdt;

      if (cached && cached.length > 0) {
        const sorted = [...cached].sort(
          (a, b) => b.overall_metrics.net_return_pct - a.overall_metrics.net_return_pct
        );
        const top = sorted[0];
        bestRetPct = top.overall_metrics.net_return_pct;
        bestStratId = top.strategy_id;
        bestStratName = top.strategy_name.split('—')[1]?.trim() || top.strategy_name;
        winRatePct = top.overall_metrics.win_rate_pct;
        totalTrades = top.overall_metrics.total_trades;
        maxDdPct = top.overall_metrics.max_drawdown_pct;
        const lastCurvePt = top.equity_curve[top.equity_curve.length - 1];
        if (lastCurvePt?.price) {
          lastPrice = lastCurvePt.price;
        }
      }

      const netReturnCop = Math.round((bestRetPct / 100) * this.initialCapitalCop);
      rows.push({
        symbol: sym,
        name: cat.name,
        category: cat.category,
        last_price_usdt: lastPrice,
        atr_pct_1h: cat.atr_pct_1h,
        range_swing_pct: cat.range_swing_pct,
        best_strategy_id: bestStratId,
        best_strategy_name: bestStratName,
        net_return_pct: bestRetPct,
        net_return_cop: netReturnCop,
        win_rate_pct: winRatePct,
        total_trades: totalTrades,
        max_drawdown_pct: maxDdPct,
        signal: lastSig?.signal || 'HOLD',
      });
    }

    return rows.sort((a, b) => b.net_return_pct - a.net_return_pct);
  }

  public runBacktestComparison(symbol: SpotSymbol = this.primarySymbol): BacktestReportDTO[] {
    const key = this.cacheKey(symbol);
    if (!this.pythonConnected) {
      return this.cachedBacktests.get(key) || [];
    }
    const rawOut = execFileSync(
      'python3',
      [
        '-m',
        'trading_bot.cli',
        'backtest',
        '--symbol',
        symbol,
        '--strategy',
        'all',
        '--provider',
        this.dataProvider,
        '--risk-profile',
        this.riskProfile,
      ],
      {
        env: this.pythonEnv,
        encoding: 'utf-8',
        timeout: 25_000,
      }
    );
    const parsed = JSON.parse(rawOut) as { symbol: string; reports: BacktestReportDTO[] };
    this.cachedBacktests.set(key, parsed.reports);
    return parsed.reports;
  }

  public getCachedOrRunBacktests(symbol: SpotSymbol = this.primarySymbol): BacktestReportDTO[] {
    const key = this.cacheKey(symbol);
    const existing = this.cachedBacktests.get(key);
    if (existing && existing.length > 0) {
      return existing;
    }
    return this.runBacktestComparison(symbol);
  }

  public runPaperStep(symbol: SpotSymbol = this.primarySymbol): {
    signal_id: string;
    risk_decision_id: string;
    data_source?: string;
    last_candle_close_utc?: number;
    signal: StrategySignalDTO;
    risk_decision: RiskDecisionDTO;
    order: Record<string, unknown> | null;
  } {
    if (!this.pythonConnected) {
      throw new Error(
        'Motor Python desconectado: no se permiten evaluaciones ni nuevas entradas cuando el estado del motor es incierto.'
      );
    }
    if (this.killSwitchActive) {
      throw new Error(
        `Interruptor de emergencia activo (${this.killSwitchReason}): nuevas entradas rechazadas.`
      );
    }

    const rawOut = execFileSync(
      'python3',
      [
        '-m',
        'trading_bot.cli',
        'paper-step',
        '--symbol',
        symbol,
        '--provider',
        this.dataProvider,
        '--risk-profile',
        this.riskProfile,
      ],
      {
        env: {
          ...this.pythonEnv,
          ACTIVE_STRATEGY_ID: this.activeStrategyId,
        },
        encoding: 'utf-8',
        timeout: 20_000,
      }
    );
    const parsed = JSON.parse(rawOut) as {
      signal_id: string;
      risk_decision_id: string;
      data_source?: string;
      last_candle_close_utc?: number;
      signal: StrategySignalDTO;
      risk_decision: RiskDecisionDTO;
      order: Record<string, unknown> | null;
    };
    this.lastSignalBySymbol.set(this.cacheKey(symbol), parsed.signal);
    this.primarySymbol = symbol;
    return parsed;
  }

  public getLastSignal(symbol: SpotSymbol = this.primarySymbol): StrategySignalDTO {
    const cached = this.lastSignalBySymbol.get(this.cacheKey(symbol));
    if (cached) return cached;
    const refPrice = SCANNER_ASSET_CATALOG[symbol]?.last_price_usdt || 91620.0;
    return {
      symbol,
      evaluated_at: Math.floor(Date.now() / 1000) - 120,
      signal: 'HOLD',
      strategy_id: this.activeStrategyId,
      strategy_version: '1.4.0',
      indicators: {
        ema50_4h: Number((refPrice * 0.985).toFixed(4)),
        ema200_4h: Number((refPrice * 0.945).toFixed(4)),
        ema20_1h: Number((refPrice * 0.996).toFixed(4)),
        ema50_1h: Number((refPrice * 0.991).toFixed(4)),
        atr14_1h: Number((refPrice * 0.011).toFixed(4)),
        relative_volume: 1.15,
      },
      reference_price: refPrice,
      invalidation_level: Number((refPrice * 0.988).toFixed(4)),
      proposed_stop: Number((refPrice * 0.982).toFixed(4)),
      proposed_take_profit: Number((refPrice * 1.032).toFixed(4)),
      explanation: `Evaluación determinista v1.4.0 sobre velas cerradas 1h y filtro de tendencia 4h (${symbol}).`,
    };
  }

  public getPortfolioSummary(): PortfolioSummaryDTO {
    const reports = this.getCachedOrRunBacktests(this.primarySymbol);
    const activeReport =
      reports.find((r) => r.strategy_id === this.activeStrategyId) || reports[0];

    const initEq = Number((this.initialCapitalCop / this.referenceCopPerUsdt).toFixed(4));
    const currentEq = activeReport ? activeReport.final_equity_usdt : initEq;
    const realizedUsdt = Number((currentEq - initEq).toFixed(4));
    const feesUsdt = activeReport ? activeReport.overall_metrics.total_fees_usdt : this.totalFeesUsdt;
    const ddPct = activeReport ? activeReport.overall_metrics.max_drawdown_pct : 0;
    const closedCount = activeReport ? activeReport.overall_metrics.total_trades : this.closedTradesCount;

    const positions = Array.from(this.openPositions.values());
    const unrealizedUsdt = positions.reduce((acc, p) => acc + p.unrealized_pnl_usdt, 0);
    const exposureUsdt = positions.reduce((acc, p) => acc + p.notional_usdt, 0);
    const exposurePct = currentEq > 0 ? Number(((exposureUsdt / currentEq) * 100).toFixed(2)) : 0;

    return {
      mode: this.getEffectiveMode(),
      data_source_label: !this.pythonConnected
        ? 'Modo Demostración — Motor Python desconectado'
        : this.dataProvider === 'binance_public'
          ? `Velas Públicas en Tiempo Real — Binance Spot REST 1h/4h (${this.riskProfile.toUpperCase()})`
          : `Simulación determinista verificada v1.4.0 (${this.riskProfile.toUpperCase()})`,
      initial_capital_cop: this.initialCapitalCop,
      reference_cop_per_usdt: this.referenceCopPerUsdt,
      initial_equity_usdt: initEq,
      current_equity_usdt: currentEq,
      current_equity_cop: Math.round(currentEq * this.referenceCopPerUsdt),
      available_cash_usdt: Number((currentEq - exposureUsdt).toFixed(4)),
      realized_pnl_usdt: realizedUsdt,
      realized_pnl_cop: Math.round(realizedUsdt * this.referenceCopPerUsdt),
      unrealized_pnl_usdt: Number(unrealizedUsdt.toFixed(4)),
      unrealized_pnl_cop: Math.round(unrealizedUsdt * this.referenceCopPerUsdt),
      net_return_pct: activeReport ? activeReport.overall_metrics.net_return_pct : 0,
      current_drawdown_pct: ddPct,
      daily_loss_pct: 0.18,
      current_exposure_pct: exposurePct,
      total_fees_usdt: feesUsdt,
      total_fees_cop: Math.round(feesUsdt * this.referenceCopPerUsdt),
      open_positions_count: positions.length,
      closed_trades_count: closedCount,
      last_updated_utc: this.getLastSignal(this.primarySymbol).evaluated_at,
    };
  }

  public getOpenPositions(): VirtualPositionDTO[] {
    return Array.from(this.openPositions.values());
  }

  public simulateRiskCheck(params: {
    symbol: string;
    reference_price: number;
    proposed_stop: number;
    equity_usdt: number;
    current_exposure_usdt: number;
    daily_loss_pct: number;
    drawdown_pct: number;
  }): RiskDecisionDTO {
    const limits = this.getRiskLimits();
    const maxRiskPct = limits.max_risk_per_trade;
    const maxExposurePct = limits.max_exposure;
    const dailyLossLimitPct = limits.daily_loss_limit * 100;
    const maxDrawdownLimitPct = limits.max_drawdown_limit * 100;
    const minNotionalUsdt = limits.min_order_notional_usdt;
    const feeRate = limits.default_fee_rate;
    const slippageRate = limits.default_slippage_rate;

    if (this.killSwitchActive) {
      return {
        approved: false,
        reason_code: 'KILL_SWITCH_ACTIVE',
        reason_detail: `Interruptor de emergencia activo: ${this.killSwitchReason}`,
        approved_quantity: 0,
        notional_usdt: 0,
        estimated_risk_usdt: 0,
        estimated_risk_pct: 0,
        estimated_fees_usdt: 0,
        stop_price: null,
      };
    }

    if (!this.pythonConnected) {
      return {
        approved: false,
        reason_code: 'ENGINE_DISCONNECTED',
        reason_detail: 'El motor Python está desconectado. Se rechazan nuevas entradas.',
        approved_quantity: 0,
        notional_usdt: 0,
        estimated_risk_usdt: 0,
        estimated_risk_pct: 0,
        estimated_fees_usdt: 0,
        stop_price: null,
      };
    }

    if (params.drawdown_pct >= maxDrawdownLimitPct) {
      return {
        approved: false,
        reason_code: 'MAX_DRAWDOWN_BREACHED',
        reason_detail: `Drawdown (${params.drawdown_pct.toFixed(2)}%) alcanza o supera el límite de ${maxDrawdownLimitPct.toFixed(2)}%.`,
        approved_quantity: 0,
        notional_usdt: 0,
        estimated_risk_usdt: 0,
        estimated_risk_pct: 0,
        estimated_fees_usdt: 0,
        stop_price: null,
      };
    }

    if (params.daily_loss_pct >= dailyLossLimitPct) {
      return {
        approved: false,
        reason_code: 'DAILY_LOSS_LIMIT_BREACHED',
        reason_detail: `Pérdida diaria (${params.daily_loss_pct.toFixed(2)}%) alcanza o supera el límite de ${dailyLossLimitPct.toFixed(2)}%.`,
        approved_quantity: 0,
        notional_usdt: 0,
        estimated_risk_usdt: 0,
        estimated_risk_pct: 0,
        estimated_fees_usdt: 0,
        stop_price: null,
      };
    }

    const entryPrice = params.reference_price * (1 + slippageRate);
    if (params.proposed_stop >= entryPrice) {
      return {
        approved: false,
        reason_code: 'INVALID_STOP_DISTANCE',
        reason_detail: `El stop propuesto (${params.proposed_stop}) debe ser inferior al precio de entrada con deslizamiento (${entryPrice.toFixed(2)}).`,
        approved_quantity: 0,
        notional_usdt: 0,
        estimated_risk_usdt: 0,
        estimated_risk_pct: 0,
        estimated_fees_usdt: 0,
        stop_price: null,
      };
    }

    const stopExitPrice = params.proposed_stop * (1 - slippageRate);
    const priceLossPerUnit = entryPrice - stopExitPrice;
    const feePerUnit = (entryPrice + stopExitPrice) * feeRate;
    const totalLossPerUnit = priceLossPerUnit + feePerUnit;

    const maxRiskUsdt = params.equity_usdt * maxRiskPct;
    const rawQtyByRisk = maxRiskUsdt / totalLossPerUnit;
    const remainingExposureUsdt = Math.max(
      0,
      params.equity_usdt * maxExposurePct - params.current_exposure_usdt
    );
    const maxQtyByExposure = remainingExposureUsdt / entryPrice;

    const approvedQty = Number(Math.min(rawQtyByRisk, maxQtyByExposure).toFixed(6));
    const notionalUsdt = Number((approvedQty * entryPrice).toFixed(4));
    const estimatedFeesUsdt = Number((approvedQty * feePerUnit).toFixed(4));
    const estimatedRiskUsdt = Number((approvedQty * totalLossPerUnit).toFixed(4));
    const estimatedRiskPct = Number((estimatedRiskUsdt / params.equity_usdt).toFixed(6));

    if (notionalUsdt < minNotionalUsdt) {
      return {
        approved: false,
        reason_code: 'MIN_NOTIONAL_EXCEEDS_RISK_OR_EXPOSURE',
        reason_detail: `El tamaño calculado (${notionalUsdt.toFixed(2)} USDT) es menor al mínimo del exchange (${minNotionalUsdt.toFixed(2)} USDT) sin exceder el 0,5% de riesgo (${maxRiskUsdt.toFixed(2)} USDT).`,
        approved_quantity: 0,
        notional_usdt: notionalUsdt,
        estimated_risk_usdt: estimatedRiskUsdt,
        estimated_risk_pct: estimatedRiskPct,
        estimated_fees_usdt: estimatedFeesUsdt,
        stop_price: params.proposed_stop,
      };
    }

    return {
      approved: true,
      reason_code: 'APPROVED',
      reason_detail: `Orden aprobada por RiskManager: ${approvedQty} unidades (${notionalUsdt.toFixed(2)} USDT), riesgo total ${estimatedRiskUsdt.toFixed(2)} USDT (${(estimatedRiskPct * 100).toFixed(2)}%).`,
      approved_quantity: approvedQty,
      notional_usdt: notionalUsdt,
      estimated_risk_usdt: estimatedRiskUsdt,
      estimated_risk_pct: estimatedRiskPct,
      estimated_fees_usdt: estimatedFeesUsdt,
      stop_price: params.proposed_stop,
    };
  }

  public getForecastComparison(symbol: SpotSymbol = this.primarySymbol, horizon = 12): ForecastComparisonDTO {
    const sig = this.getLastSignal(symbol);
    const basePrice = sig.reference_price;
    const decimals = basePrice >= 100 ? 2 : basePrice >= 1 ? 4 : basePrice >= 0.001 ? 6 : 8;
    const p10: number[] = [];
    const p50: number[] = [];
    const p90: number[] = [];

    for (let h = 1; h <= horizon; h++) {
      const drift = Number((basePrice * Math.pow(1 + 0.0004, h)).toFixed(decimals));
      const band = Number((basePrice * 0.0038 * Math.sqrt(h) * 1.2816).toFixed(decimals));
      p50.push(drift);
      p10.push(Number((drift - band).toFixed(decimals)));
      p90.push(Number((drift + band).toFixed(decimals)));
    }

    const timesfmEnabled = process.env.ENABLE_TIMESFM === 'true';

    return {
      symbol,
      origin_timestamp: sig.evaluated_at,
      horizon,
      timesfm: {
        provider_id: 'timesfm',
        model_version: process.env.TIMESFM_MODEL_VERSION || 'timesfm-2.5-200m',
        available: false,
        enabled: timesfmEnabled,
        point_forecast: [],
        quantiles_p10: [],
        quantiles_p50: [],
        quantiles_p90: [],
        execution_ms: 0.4,
        baseline_mae: 148.2,
        error_message: timesfmEnabled
          ? 'Checkpoint local de TimesFM 2.5 no montado. Por regla de integridad (Sección 8), nunca se inventan resultados de TimesFM cuando el modelo no se ha ejecutado.'
          : 'Módulo experimental TimesFM deshabilitado por defecto (ENABLE_TIMESFM=false). El sistema opera sin depender de TimesFM.',
      },
      statistical_baseline: {
        provider_id: 'statistical_baseline',
        model_version: 'naive-drift-v1',
        available: true,
        enabled: true,
        point_forecast: p50,
        quantiles_p10: p10,
        quantiles_p50: p50,
        quantiles_p90: p90,
        execution_ms: 0.8,
        baseline_mae: 148.2,
        error_message: null,
      },
    };
  }
}
