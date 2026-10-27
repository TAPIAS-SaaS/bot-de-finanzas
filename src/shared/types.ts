/**
 * Contratos tipados compartidos entre el Frontend React y el Servidor Node.js / Motor Python.
 */

export type TradingMode = 'demo' | 'paper' | 'live';
export type SignalAction = 'BUY' | 'SELL' | 'HOLD';
export type MarketRegime = 'TRENDING' | 'MEAN_REVERTING' | 'RANGING' | 'VOLATILE' | 'UNCERTAIN';

export interface StrategySignalDTO {
  symbol: string;
  evaluated_at: number;
  signal: SignalAction;
  strategy_id: string;
  strategy_version: string;
  indicators: Record<string, number>;
  reference_price: number;
  invalidation_level: number | null;
  proposed_stop: number | null;
  proposed_take_profit: number | null;
  explanation: string;
}

export interface RiskDecisionDTO {
  approved: boolean;
  reason_code: string;
  reason_detail: string;
  approved_quantity: number;
  notional_usdt: number;
  estimated_risk_usdt: number;
  estimated_risk_pct: number;
  estimated_fees_usdt: number;
  stop_price: number | null;
}

export interface VirtualPositionDTO {
  symbol: string;
  strategy_id: string;
  quantity: number;
  entry_price: number;
  mark_price: number;
  stop_price: number;
  take_profit_price: number | null;
  opened_at: number;
  entry_fee_usdt: number;
  unrealized_pnl_usdt: number;
  unrealized_pnl_cop: number;
  notional_usdt: number;
}

export interface PortfolioSummaryDTO {
  mode: TradingMode;
  data_source_label: string;
  initial_capital_cop: number;
  reference_cop_per_usdt: number;
  initial_equity_usdt: number;
  current_equity_usdt: number;
  current_equity_cop: number;
  available_cash_usdt: number;
  realized_pnl_usdt: number;
  realized_pnl_cop: number;
  unrealized_pnl_usdt: number;
  unrealized_pnl_cop: number;
  net_return_pct: number;
  current_drawdown_pct: number;
  daily_loss_pct: number;
  current_exposure_pct: number;
  total_fees_usdt: number;
  total_fees_cop: number;
  open_positions_count: number;
  closed_trades_count: number;
  last_updated_utc: number;
}

export interface SimulatedTradeDTO {
  trade_id: string;
  strategy_id: string;
  symbol: string;
  segment: 'development' | 'validation' | 'out_of_sample' | 'paper';
  signal_timestamp: number;
  entry_timestamp: number;
  exit_timestamp: number;
  entry_price: number;
  exit_price: number;
  quantity: number;
  gross_pnl_usdt: number;
  fees_usdt: number;
  net_pnl_usdt: number;
  net_return_pct: number;
  exit_reason: string;
}

export interface SegmentMetricsDTO {
  segment: string;
  start_timestamp: number;
  end_timestamp: number;
  initial_equity_usdt: number;
  final_equity_usdt: number;
  gross_return_pct: number;
  net_return_pct: number;
  benchmark_buy_hold_pct: number;
  total_trades: number;
  win_rate_pct: number;
  profit_factor: number;
  expectancy_usdt: number;
  max_drawdown_pct: number;
  total_fees_usdt: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  avg_exposure_pct: number;
  sample_warning: string | null;
}

export interface AcceptanceCheckDTO {
  passed: boolean;
  min_trades_required: number;
  observed_oos_trades: number;
  oos_net_return_pct: number;
  oos_profit_factor: number;
  oos_max_drawdown_pct: number;
  cost_stress_net_return_pct: number;
  reasons: string[];
}

export interface BacktestReportDTO {
  run_id: string;
  strategy_id: string;
  strategy_name: string;
  symbol: string;
  initial_capital_cop: number;
  reference_cop_per_usdt: number;
  initial_equity_usdt: number;
  final_equity_usdt: number;
  final_equity_cop: number;
  overall_metrics: SegmentMetricsDTO;
  development_metrics: SegmentMetricsDTO;
  validation_metrics: SegmentMetricsDTO;
  out_of_sample_metrics: SegmentMetricsDTO;
  acceptance: AcceptanceCheckDTO;
  trades: SimulatedTradeDTO[];
  equity_curve: Array<{
    timestamp: number;
    equity_usdt: number;
    equity_cop: number;
    drawdown_pct: number;
    price: number;
  }>;
}

export interface AdvisorAnalysisDTO {
  market_regime: MarketRegime;
  recommendation: 'BUY' | 'SELL' | 'HOLD' | 'PAUSE';
  confidence: number;
  supporting_factors: string[];
  risk_factors: string[];
  strategy_id: string | null;
  reason: string;
  data_timestamp: string;
  model_id: string;
  warnings: string[];
  source: 'gemini_live_api' | 'deterministic_fallback';
}

export interface ForecastComparisonDTO {
  symbol: string;
  origin_timestamp: number;
  horizon: number;
  timesfm: {
    provider_id: string;
    model_version: string;
    available: boolean;
    enabled: boolean;
    point_forecast: number[];
    quantiles_p10: number[];
    quantiles_p50: number[];
    quantiles_p90: number[];
    execution_ms: number;
    baseline_mae: number | null;
    error_message: string | null;
  };
  statistical_baseline: {
    provider_id: string;
    model_version: string;
    available: boolean;
    enabled: boolean;
    point_forecast: number[];
    quantiles_p10: number[];
    quantiles_p50: number[];
    quantiles_p90: number[];
    execution_ms: number;
    baseline_mae: number | null;
    error_message: string | null;
  };
}

export interface DecisionAuditRowDTO {
  signal_id: string;
  created_at: number;
  symbol: string;
  strategy_id: string;
  signal: SignalAction;
  reference_price: number;
  proposed_stop: number | null;
  explanation: string;
  risk_decision_id: string;
  approved: number;
  reason_code: string;
  reason_detail: string;
  approved_quantity: number;
  notional_usdt: number;
  estimated_risk_usdt: number;
  order_id: string | null;
  client_order_id: string | null;
  order_status: string | null;
  fill_price: number | null;
}

export interface EngineStatusDTO {
  effective_mode: TradingMode;
  python_engine_connected: boolean;
  python_engine_transport: 'python3_subprocess_bridge' | 'disconnected_demo';
  paper_trading_active: boolean;
  kill_switch_active: boolean;
  kill_switch_reason: string;
  active_strategy_id: string;
  primary_symbol: string;
  candidate_symbols: string[];
  last_data_timestamp: number;
  data_staleness_seconds: number;
  risk_limits: {
    max_risk_per_trade: number;
    max_exposure: number;
    daily_loss_limit: number;
    max_drawdown_limit: number;
    max_concurrent_positions: number;
    min_order_notional_usdt: number;
    default_fee_rate: number;
    default_slippage_rate: number;
    allow_leverage: boolean;
    allow_margin: boolean;
    allow_short: boolean;
    allow_withdrawals: boolean;
  };
  live_readiness: {
    ready_for_live: boolean;
    checks: Record<string, boolean>;
    blocking_reasons: string[];
  };
  audit_events: Array<{
    event_id: number;
    created_at: number;
    severity: string;
    category: string;
    message: string;
  }>;
}
