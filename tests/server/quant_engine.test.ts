import test from 'node:test';
import assert from 'node:assert/strict';
import { AdvisorResponseZodSchema, ServerGeminiAdvisor } from '../../server/services/geminiAdvisor';
import { NodeSQLiteAuditRepository } from '../../server/services/sqliteStore';
import { PythonEngineBridge } from '../../server/services/pythonBridge';

test('NodeSQLiteAuditRepository inicializa esquema en memoria, redacta secretos y exporta CSV', () => {
  const repo = new NodeSQLiteAuditRepository(':memory:');
  repo.logAuditEvent('WARN', 'SECURITY_TEST', 'Intento con EXCHANGE_API_KEY=super_secreto_123');
  const events = repo.getAuditEvents(5);
  assert.equal(events.length >= 1, true);
  assert.equal(events[0].message.includes('super_secreto_123'), false);
  assert.equal(events[0].message.includes('[REDACTADO]'), true);

  const csv = repo.exportDecisionHistoryCSV();
  assert.equal(csv.startsWith('signal_id,created_at,symbol'), true);
});

test('PythonEngineBridge arranca en modo paper, ejecuta backtests 60/20/20 y aplica RiskManager', () => {
  const repo = new NodeSQLiteAuditRepository(':memory:');
  const bridge = new PythonEngineBridge(repo);

  assert.equal(bridge.getEffectiveMode(), 'paper');
  assert.equal(bridge.isPythonConnected(), true);

  const reports = bridge.getCachedOrRunBacktests('BTC/USDT');
  assert.equal(reports.length, 3);
  const stratIds = reports.map((r) => r.strategy_id);
  assert.deepEqual(stratIds, [
    'trend_following_v1',
    'mean_reversion_v1',
    'range_breakout_v1',
  ]);

  // Verificar cálculo de posición válida en RiskManager
  const approvedDec = bridge.simulateRiskCheck({
    symbol: 'BTC/USDT',
    reference_price: 90_000,
    proposed_stop: 89_100,
    equity_usdt: 95.24,
    current_exposure_usdt: 0,
    daily_loss_pct: 0.2,
    drawdown_pct: 0.8,
  });
  assert.equal(approvedDec.approved, true);
  assert.equal(approvedDec.notional_usdt >= 5.0, true);
  assert.equal(approvedDec.estimated_risk_pct <= 0.0051, true);

  // Verificar rechazo cuando el mínimo de orden excede el 0.5% de riesgo
  const rejectedMinNotional = bridge.simulateRiskCheck({
    symbol: 'BTC/USDT',
    reference_price: 90_000,
    proposed_stop: 65_000,
    equity_usdt: 95.24,
    current_exposure_usdt: 0,
    daily_loss_pct: 0.1,
    drawdown_pct: 0.5,
  });
  assert.equal(rejectedMinNotional.approved, false);
  assert.equal(rejectedMinNotional.reason_code, 'MIN_NOTIONAL_EXCEEDS_RISK_OR_EXPOSURE');

  // Verificar cambio a Modo Arriesgado Alta Convicción (2.0% riesgo/op y 95% exposición Spot)
  bridge.setRiskProfile('aggressive');
  assert.equal(bridge.getRiskProfile(), 'aggressive');
  assert.equal(bridge.getRiskLimits().max_risk_per_trade, 0.02);
  assert.equal(bridge.getRiskLimits().max_exposure, 0.95);
  const aggrDec = bridge.simulateRiskCheck({
    symbol: 'BTC/USDT',
    reference_price: 90_000,
    proposed_stop: 88_200,
    equity_usdt: 95.24,
    current_exposure_usdt: 0,
    daily_loss_pct: 0.2,
    drawdown_pct: 0.8,
  });
  assert.equal(aggrDec.approved, true);
  assert.equal(aggrDec.notional_usdt > 50.0, true);
  assert.equal(aggrDec.estimated_risk_pct <= 0.0205, true);

  // Verificar que el interruptor de emergencia bloquea nuevas órdenes
  bridge.activateKillSwitch('Prueba unitaria de emergencia');
  assert.equal(bridge.getKillSwitchState().active, true);
  const rejectedKill = bridge.simulateRiskCheck({
    symbol: 'BTC/USDT',
    reference_price: 90_000,
    proposed_stop: 89_100,
    equity_usdt: 95.24,
    current_exposure_usdt: 0,
    daily_loss_pct: 0,
    drawdown_pct: 0,
  });
  assert.equal(rejectedKill.approved, false);
  assert.equal(rejectedKill.reason_code, 'KILL_SWITCH_ACTIVE');

  // Verificar Radar Escáner Multi-Moneda (14 pares Spot de alta liquidez y alto movimiento)
  const scanner = bridge.getMarketScanner();
  assert.equal(scanner.length, 14);
  assert.equal(scanner[0].net_return_pct >= scanner[scanner.length - 1].net_return_pct, true);
  assert.equal(scanner.some((r) => r.symbol === 'PEPE/USDT'), true);
  assert.equal(scanner.some((r) => r.symbol === 'INJ/USDT'), true);
  assert.equal(scanner.some((r) => r.symbol === 'RENDER/USDT'), true);
  assert.equal(scanner.some((r) => r.symbol === 'WIF/USDT'), true);
  assert.equal(scanner.some((r) => r.symbol === 'SOL/USDT'), true);
});

test('ServerGeminiAdvisor valida esquema JSON estricto y rechaza estrategias fuera de lista', () => {
  const validPayload = {
    market_regime: 'TRENDING',
    recommendation: 'HOLD',
    confidence: 0.55,
    supporting_factors: ['EMA 50 > EMA 200 en 4h'],
    risk_factors: ['Proximidad a resistencia horaria'],
    strategy_id: 'trend_following_v1',
    reason: 'Esperar confirmación de volumen al cierre de vela.',
    data_timestamp: '2026-10-27T12:00:00Z',
    model_id: 'gemini-3.8-flash',
    warnings: ['Confianza no calibrada'],
  };
  const parsed = AdvisorResponseZodSchema.safeParse(validPayload);
  assert.equal(parsed.success, true);

  const invalidPayload = {
    ...validPayload,
    confidence: 1.5,
    strategy_id: 'estrategia_no_autorizada',
  };
  const failed = AdvisorResponseZodSchema.safeParse(invalidPayload);
  assert.equal(failed.success, false);

  const advisor = new ServerGeminiAdvisor();
  const fallback = advisor.buildSafeFallback(
    {
      symbol: 'BTC/USDT',
      referencePrice: 90_000,
      indicators: { ema50_4h: 91000, ema200_4h: 89000 },
      lastSignal: 'HOLD',
      activeStrategyId: 'trend_following_v1',
    },
    '2026-10-27T12:00:00Z',
    'Sin clave API en test'
  );
  assert.equal(fallback.recommendation, 'HOLD');
  assert.equal(fallback.source, 'deterministic_fallback');
});
