/**
 * Middleware de seguridad, límite de frecuencia (rate limiting), validación Zod
 * y protección de endpoints administrativos.
 */

import type { Request, Response, NextFunction } from 'express';
import { z } from 'zod';
import { SUPPORTED_SPOT_SYMBOLS } from '../../src/shared/types';

const requestCounts = new Map<string, { count: number; resetAt: number }>();

export function rateLimitMiddleware(maxRequestsPerMinute = 120) {
  return (req: Request, res: Response, next: NextFunction) => {
    const ip = req.ip || req.socket.remoteAddress || 'local';
    const now = Date.now();
    const record = requestCounts.get(ip);
    if (!record || now > record.resetAt) {
      requestCounts.set(ip, { count: 1, resetAt: now + 60_000 });
      return next();
    }
    record.count += 1;
    if (record.count > maxRequestsPerMinute) {
      return res.status(429).json({
        error: 'RATE_LIMIT_EXCEEDED',
        message: 'Demasiadas peticiones por minuto. Espere antes de reintentar.',
      });
    }
    return next();
  };
}

/**
 * Valida la cabecera de autorización administrativa en operaciones de mutación.
 * Permite el token configurado en ADMIN_API_TOKEN o el token de sesión del terminal local.
 */
export function requireAdminAuth(req: Request, res: Response, next: NextFunction) {
  const configuredToken = process.env.ADMIN_API_TOKEN || 'dev-local-admin-token-change-in-prod';
  const provided =
    req.header('x-admin-token') ||
    req.header('authorization')?.replace(/^Bearer\s+/i, '') ||
    '';

  if (!provided || provided !== configuredToken) {
    return res.status(401).json({
      error: 'UNAUTHORIZED_ADMIN_ACTION',
      message:
        'Las operaciones administrativas requieren cabecera x-admin-token válida.',
    });
  }
  return next();
}

export const SpotSymbolEnum = z.enum(SUPPORTED_SPOT_SYMBOLS);

export const RunBacktestSchema = z.object({
  symbol: SpotSymbolEnum.default('BTC/USDT'),
  strategy_id: z
    .enum(['all', 'trend_following_v1', 'mean_reversion_v1', 'range_breakout_v1'])
    .default('all'),
});

export const PaperStepSchema = z.object({
  symbol: SpotSymbolEnum.default('BTC/USDT'),
  strategy_id: z
    .enum(['trend_following_v1', 'mean_reversion_v1', 'range_breakout_v1'])
    .optional(),
});

export const KillSwitchResumeSchema = z.object({
  confirmation_phrase: z.literal('CONFIRMO_REVISION_DE_REGISTROS'),
});

export const RiskSimulationSchema = z.object({
  symbol: SpotSymbolEnum.default('BTC/USDT'),
  reference_price: z.number().positive(),
  proposed_stop: z.number().positive(),
  equity_usdt: z.number().positive(),
  current_exposure_usdt: z.number().min(0).default(0),
  daily_loss_pct: z.number().min(0).max(100).default(0),
  drawdown_pct: z.number().min(0).max(100).default(0),
});
