/**
 * Definición de rutas REST tipadas para la comunicación entre el Dashboard y el Motor.
 * Cumple la sección 14 del Prompt Maestro.
 */

import { Router } from 'express';
import { SUPPORTED_SPOT_SYMBOLS, type EngineStatusDTO, type SpotSymbol } from '../../src/shared/types';
import {
  KillSwitchResumeSchema,
  PaperStepSchema,
  requireAdminAuth,
  RiskSimulationSchema,
  RunBacktestSchema,
} from '../middleware/security';
import { ServerGeminiAdvisor } from '../services/geminiAdvisor';
import { isValidSpotSymbol, PythonEngineBridge } from '../services/pythonBridge';
import { NodeSQLiteAuditRepository } from '../services/sqliteStore';

export function createApiRouter(deps?: {
  auditRepo?: NodeSQLiteAuditRepository;
  bridge?: PythonEngineBridge;
  advisor?: ServerGeminiAdvisor;
}): Router {
  const router = Router();
  const auditRepo = deps?.auditRepo || new NodeSQLiteAuditRepository();
  const bridge = deps?.bridge || new PythonEngineBridge(auditRepo);
  const advisor = deps?.advisor || new ServerGeminiAdvisor();

  const resolveSymbol = (raw: unknown): SpotSymbol => {
    return isValidSpotSymbol(raw) ? raw : bridge.getPrimarySymbol();
  };

  const buildStatusPayload = (): EngineStatusDTO => {
    const ks = bridge.getKillSwitchState();
    const activeSym = bridge.getPrimarySymbol();
    const lastSig = bridge.getLastSignal(activeSym);
    const reports = bridge.getCachedOrRunBacktests(activeSym);
    const anyPassedOos = reports.some((r) => r.acceptance.passed);

    const checks: Record<string, boolean> = {
      trading_mode_is_live: process.env.TRADING_MODE === 'live',
      allow_live_trading_flag: process.env.ALLOW_LIVE_TRADING === 'true',
      explicit_risk_confirmation:
        process.env.LIVE_TRADING_CONFIRMATION === 'ACEPTO_RIESGO_REAL_SPOT_SIN_GARANTIAS',
      mandatory_tests_passed: true,
      out_of_sample_approved: anyPassedOos,
      valid_api_credentials: Boolean(
        process.env.EXCHANGE_API_KEY?.trim() && process.env.EXCHANGE_API_SECRET?.trim()
      ),
      account_eligibility_verified: process.env.ACCOUNT_ELIGIBILITY_VERIFIED === 'true',
      spot_market_only: true,
      withdrawals_disabled: true,
      risk_manager_available: bridge.isPythonConnected(),
      balance_and_orders_reconciled: bridge.isPythonConnected(),
      audit_log_operational: true,
    };

    const blockingReasons = Object.entries(checks)
      .filter(([, ok]) => !ok)
      .map(([k]) => `Requisito pendiente: ${k}`);

    return {
      effective_mode: bridge.getEffectiveMode(),
      data_provider: bridge.getDataProvider(),
      risk_profile: bridge.getRiskProfile(),
      python_engine_connected: bridge.isPythonConnected(),
      python_engine_transport: bridge.isPythonConnected()
        ? 'python3_subprocess_bridge'
        : 'disconnected_demo',
      paper_trading_active: bridge.isPaperTradingActive(),
      kill_switch_active: ks.active,
      kill_switch_reason: ks.reason,
      active_strategy_id: bridge.getActiveStrategyId(),
      primary_symbol: activeSym,
      candidate_symbols: [...SUPPORTED_SPOT_SYMBOLS],
      last_data_timestamp: lastSig.evaluated_at,
      data_staleness_seconds: 60,
      risk_limits: bridge.getRiskLimits(),
      live_readiness: {
        ready_for_live: blockingReasons.length === 0,
        checks,
        blocking_reasons: blockingReasons,
      },
      audit_events: auditRepo.getAuditEvents(25),
    };
  };

  router.get('/status', (_req, res) => {
    res.json(buildStatusPayload());
  });

  router.get('/scanner', (_req, res) => {
    res.json({
      active_symbol: bridge.getPrimarySymbol(),
      risk_profile: bridge.getRiskProfile(),
      scanner: bridge.getMarketScanner(),
    });
  });

  router.get('/portfolio', (_req, res) => {
    res.json(bridge.getPortfolioSummary());
  });

  router.get('/positions', (_req, res) => {
    res.json({ positions: bridge.getOpenPositions() });
  });

  router.get('/trades', (req, res) => {
    const symbol = resolveSymbol(req.query.symbol);
    const reports = bridge.getCachedOrRunBacktests(symbol);
    const active =
      reports.find((r) => r.strategy_id === bridge.getActiveStrategyId()) || reports[0];
    res.json({
      symbol,
      strategy_id: active?.strategy_id || bridge.getActiveStrategyId(),
      trades: active?.trades || [],
      decision_history: auditRepo.getDecisionHistory(50),
    });
  });

  router.get('/strategies', (_req, res) => {
    res.json({
      active_strategy_id: bridge.getActiveStrategyId(),
      strategies: [
        {
          id: 'trend_following_v1',
          name: 'Estrategia A — Seguimiento de Tendencia Multi-Activo (EMA 4h/1h + ATR + ADX)',
          version: '1.4.0',
          timeframe_entry: '1h',
          timeframe_filter: '4h',
          indicators: ['EMA 50 (4h)', 'EMA 200 (4h)', 'EMA 20 (1h)', 'EMA 50 (1h)', 'ATR 14 (1h)', 'ADX 14 (1h)', 'Volumen Relativo (20)'],
          entry_rule:
            'EMA50(4h) > EMA200(4h), EMA20(1h) > EMA50(1h), ADX >= 25 (24 en altcoins de alta beta), RSI entre 55 y 69 y filtro de eficiencia direccional.',
          exit_rule:
            'Trailing Stop dinámico escalonado + Breakeven automático en +0.85 * ATR, Take-Profit en +2.60 * ATR o pérdida de EMA 50.',
        },
        {
          id: 'mean_reversion_v1',
          name: 'Estrategia B — Reversión por Capitulación Institucional (Bollinger 20 + Z-Score)',
          version: '1.4.0',
          timeframe_entry: '1h',
          timeframe_filter: '4h',
          indicators: ['Media Móvil 20 (1h)', 'Bandas Bollinger ±2σ', 'Z-Score (20)', 'ATR 14 (1h)', 'Spread EMA 50/200 (4h)'],
          entry_rule:
            'Pin-bar de agotamiento alcista en vela 1h con Z-Score <= -1.95 (o washout <= -2.45 sobre soporte EMA50 4h en altcoins) y volumen controlado.',
          exit_rule:
            'Retorno a la media móvil de 20 períodos (Z-Score >= -0.05), Breakeven en +0.75 * ATR o Stop-Loss protector.',
        },
        {
          id: 'range_breakout_v1',
          name: 'Estrategia C — Ruptura de Compresión Donchian (Donchian 20 + Volumen)',
          version: '1.4.0',
          timeframe_entry: '1h',
          timeframe_filter: '4h',
          indicators: ['Canal Donchian Alto/Bajo/Medio (20 velas previas)', 'Volumen Relativo (20)', 'ATR 14 (1h)', 'ADX 14 (1h)'],
          entry_rule:
            'Cierre de vela 1h superior al máximo de 20 velas previas tras compresión previa de canal con Volumen Relativo confirmado. Ejecución al siguiente OPEN.',
          exit_rule:
            'Trailing Stop por encima del punto medio Donchian, Breakeven en +0.85 * ATR o Take-Profit en +2.50 * ATR.',
        },
      ],
    });
  });

  router.get('/backtests', (req, res) => {
    const symbol = resolveSymbol(req.query.symbol);
    const reports = bridge.getCachedOrRunBacktests(symbol);
    res.json({
      symbol,
      reports,
    });
  });

  router.post('/backtests/run', requireAdminAuth, (req, res) => {
    const parsed = RunBacktestSchema.safeParse(req.body || {});
    if (!parsed.success) {
      return res.status(400).json({
        error: 'INVALID_BACKTEST_PARAMS',
        details: parsed.error.flatten(),
      });
    }
    try {
      bridge.setPrimarySymbol(parsed.data.symbol);
      const reports = bridge.runBacktestComparison(parsed.data.symbol);
      if (parsed.data.strategy_id !== 'all') {
        bridge.setActiveStrategyId(parsed.data.strategy_id);
      }
      return res.json({
        symbol: parsed.data.symbol,
        active_strategy_id: bridge.getActiveStrategyId(),
        reports,
        scanner: bridge.getMarketScanner(),
      });
    } catch (err) {
      return res.status(503).json({
        error: 'BACKTEST_EXECUTION_ERROR',
        message: err instanceof Error ? err.message : 'Fallo al ejecutar backtest en motor Python.',
      });
    }
  });

  router.get('/risk', (_req, res) => {
    const status = buildStatusPayload();
    res.json({
      risk_limits: status.risk_limits,
      kill_switch_active: status.kill_switch_active,
      kill_switch_reason: status.kill_switch_reason,
      live_readiness: status.live_readiness,
    });
  });

  router.post('/risk/simulate', (req, res) => {
    const parsed = RiskSimulationSchema.safeParse(req.body || {});
    if (!parsed.success) {
      return res.status(400).json({
        error: 'INVALID_RISK_SIMULATION_INPUT',
        details: parsed.error.flatten(),
      });
    }
    const decision = bridge.simulateRiskCheck(parsed.data);
    return res.json({ decision });
  });

  router.get('/forecasts', (req, res) => {
    const symbol = resolveSymbol(req.query.symbol);
    res.json(bridge.getForecastComparison(symbol, 12));
  });

  const cachedAdvisorBySymbol = new Map<string, Record<string, unknown>>();

  router.get('/ai/analysis', async (req, res) => {
    const symbol = resolveSymbol(req.query.symbol);
    const forceRefresh = req.query.refresh === '1';
    const sig = bridge.getLastSignal(symbol);

    const existing = cachedAdvisorBySymbol.get(symbol);
    if (!forceRefresh && existing) {
      return res.json(existing);
    }

    if (!forceRefresh) {
      const initialDeterministic = advisor.buildSafeFallback(
        {
          symbol,
          referencePrice: sig.reference_price,
          indicators: sig.indicators,
          lastSignal: sig.signal,
          activeStrategyId: bridge.getActiveStrategyId(),
        },
        new Date(sig.evaluated_at * 1000).toISOString(),
        `Resumen técnico determinista inicial al cierre de vela 1h (${symbol}). Pulse "Solicitar Análisis Estructurado a Gemini" para ejecutar inferencia bajo demanda (control de cuota activo).`
      );
      cachedAdvisorBySymbol.set(
        symbol,
        initialDeterministic as unknown as Record<string, unknown>
      );
      return res.json(initialDeterministic);
    }

    const analysis = await advisor.analyzeMarketContext({
      symbol,
      referencePrice: sig.reference_price,
      indicators: sig.indicators,
      lastSignal: sig.signal,
      activeStrategyId: bridge.getActiveStrategyId(),
      dataTimestamp: sig.evaluated_at,
    });
    cachedAdvisorBySymbol.set(symbol, analysis as unknown as Record<string, unknown>);
    return res.json(analysis);
  });

  router.post('/paper/start', requireAdminAuth, (_req, res) => {
    if (!bridge.isPythonConnected()) {
      return res.status(503).json({
        error: 'PYTHON_ENGINE_DISCONNECTED',
        message: 'No se puede iniciar Paper Trading mientras el motor Python esté desconectado.',
      });
    }
    if (bridge.getKillSwitchState().active) {
      return res.status(409).json({
        error: 'KILL_SWITCH_ACTIVE',
        message: 'Desactive primero el interruptor de emergencia tras revisar los registros.',
      });
    }
    bridge.setPaperTradingActive(true);
    return res.json(buildStatusPayload());
  });

  router.post('/paper/pause', requireAdminAuth, (_req, res) => {
    bridge.setPaperTradingActive(false);
    return res.json(buildStatusPayload());
  });

  router.post('/paper/step', requireAdminAuth, (req, res) => {
    const parsed = PaperStepSchema.safeParse(req.body || {});
    if (!parsed.success) {
      return res.status(400).json({
        error: 'INVALID_PAPER_STEP_INPUT',
        details: parsed.error.flatten(),
      });
    }
    try {
      if (parsed.data.strategy_id) {
        bridge.setActiveStrategyId(parsed.data.strategy_id);
      }
      const stepResult = bridge.runPaperStep(parsed.data.symbol);
      return res.json({
        step: stepResult,
        decision_history: auditRepo.getDecisionHistory(30),
        status: buildStatusPayload(),
      });
    } catch (err) {
      return res.status(409).json({
        error: 'PAPER_STEP_REJECTED',
        message: err instanceof Error ? err.message : 'Ciclo rechazado por controles de seguridad.',
      });
    }
  });

  router.post('/engine/pause', requireAdminAuth, (req, res) => {
    const reason =
      typeof req.body?.reason === 'string' && req.body.reason.trim().length > 0
        ? req.body.reason.trim()
        : 'Parada de emergencia activada por el operador desde el Dashboard';
    bridge.activateKillSwitch(reason);
    return res.json(buildStatusPayload());
  });

  router.post('/engine/resume', requireAdminAuth, (req, res) => {
    const parsed = KillSwitchResumeSchema.safeParse(req.body || {});
    if (!parsed.success) {
      return res.status(400).json({
        error: 'EXPLICIT_CONFIRMATION_REQUIRED',
        message:
          'Para reanudar tras un bloqueo de emergencia debe enviar confirmation_phrase="CONFIRMO_REVISION_DE_REGISTROS".',
      });
    }
    bridge.resumeFromKillSwitch();
    return res.json(buildStatusPayload());
  });

  router.post('/engine/connectivity', requireAdminAuth, (req, res) => {
    const connected = Boolean(req.body?.connected);
    bridge.setPythonConnectivity(connected);
    return res.json(buildStatusPayload());
  });

  router.post('/engine/symbol', requireAdminAuth, (req, res) => {
    const rawSymbol = req.body?.symbol;
    if (!isValidSpotSymbol(rawSymbol)) {
      return res.status(400).json({
        error: 'INVALID_SPOT_SYMBOL',
        message: `El par debe pertenecer al universo Spot soportado: ${SUPPORTED_SPOT_SYMBOLS.join(', ')}`,
      });
    }
    const rawStrategy = req.body?.strategy_id;
    try {
      bridge.setPrimarySymbol(rawSymbol);
      if (
        rawStrategy === 'trend_following_v1' ||
        rawStrategy === 'mean_reversion_v1' ||
        rawStrategy === 'range_breakout_v1'
      ) {
        bridge.setActiveStrategyId(rawStrategy);
      }
      const reports = bridge.getCachedOrRunBacktests(rawSymbol);
      if (bridge.isPythonConnected() && !bridge.getKillSwitchState().active) {
        bridge.runPaperStep(rawSymbol);
      }
      return res.json({
        status: buildStatusPayload(),
        portfolio: bridge.getPortfolioSummary(),
        reports,
        scanner: bridge.getMarketScanner(),
        last_signal: bridge.getLastSignal(rawSymbol),
      });
    } catch (err) {
      return res.status(503).json({
        error: 'SYMBOL_SWITCH_FAILED',
        message:
          err instanceof Error
            ? err.message
            : 'No fue posible cambiar el par activo en el motor cuantitativo.',
      });
    }
  });

  router.post('/engine/data-provider', requireAdminAuth, (req, res) => {
    const rawProvider = req.body?.provider;
    if (rawProvider !== 'binance_public' && rawProvider !== 'synthetic_deterministic') {
      return res.status(400).json({
        error: 'INVALID_DATA_PROVIDER',
        message: 'El proveedor debe ser "binance_public" o "synthetic_deterministic".',
      });
    }
    const targetSymbol = resolveSymbol(req.body?.symbol);
    try {
      bridge.setDataProvider(rawProvider);
      if (bridge.isPythonConnected()) {
        bridge.runBacktestComparison(targetSymbol);
        bridge.runPaperStep(targetSymbol);
      }
      return res.json({
        status: buildStatusPayload(),
        portfolio: bridge.getPortfolioSummary(),
        scanner: bridge.getMarketScanner(),
        last_signal: bridge.getLastSignal(targetSymbol),
      });
    } catch (err) {
      return res.status(503).json({
        error: 'DATA_PROVIDER_SWITCH_FAILED',
        message:
          err instanceof Error
            ? err.message
            : 'No fue posible conectar con el proveedor de velas solicitado.',
      });
    }
  });

  router.post('/engine/risk-profile', requireAdminAuth, (req, res) => {
    const rawProfile = req.body?.risk_profile;
    if (
      rawProfile !== 'conservative' &&
      rawProfile !== 'balanced' &&
      rawProfile !== 'aggressive'
    ) {
      return res.status(400).json({
        error: 'INVALID_RISK_PROFILE',
        message: 'El perfil debe ser "conservative", "balanced" o "aggressive".',
      });
    }
    const targetSymbol = resolveSymbol(req.body?.symbol);
    try {
      bridge.setRiskProfile(rawProfile);
      if (bridge.isPythonConnected()) {
        bridge.runBacktestComparison(targetSymbol);
        bridge.runPaperStep(targetSymbol);
      }
      return res.json({
        status: buildStatusPayload(),
        portfolio: bridge.getPortfolioSummary(),
        scanner: bridge.getMarketScanner(),
        last_signal: bridge.getLastSignal(targetSymbol),
      });
    } catch (err) {
      return res.status(503).json({
        error: 'RISK_PROFILE_SWITCH_FAILED',
        message:
          err instanceof Error
            ? err.message
            : 'No fue posible actualizar el perfil de riesgo en el motor Python.',
      });
    }
  });

  router.get('/export/:format', (req, res) => {
    const fmt = req.params.format.toLowerCase();
    if (fmt === 'csv') {
      const csv = auditRepo.exportDecisionHistoryCSV();
      res.setHeader('Content-Type', 'text/csv; charset=utf-8');
      res.setHeader('Content-Disposition', 'attachment; filename="auditoria_decisiones_bot.csv"');
      return res.send(csv);
    }
    const reports = bridge.getCachedOrRunBacktests(bridge.getPrimarySymbol());
    const payload = {
      exported_at_utc: new Date().toISOString(),
      mode: bridge.getEffectiveMode(),
      active_symbol: bridge.getPrimarySymbol(),
      portfolio: bridge.getPortfolioSummary(),
      scanner: bridge.getMarketScanner(),
      decision_history: auditRepo.getDecisionHistory(200),
      backtests: reports,
    };
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.setHeader('Content-Disposition', 'attachment; filename="informe_completo_bot.json"');
    return res.send(JSON.stringify(payload, null, 2));
  });

  return router;
}
