/**
 * Creación de la aplicación Express (`server/index.ts`).
 * Separada del arranque de Vite para poder ser probada de forma aislada en tests automatizados.
 */

import express from 'express';
import { rateLimitMiddleware } from './middleware/security';
import { createApiRouter } from './routes/api';
import { ServerGeminiAdvisor } from './services/geminiAdvisor';
import { PythonEngineBridge } from './services/pythonBridge';
import { NodeSQLiteAuditRepository } from './services/sqliteStore';

export function createExpressApp(customDbPath?: string) {
  const app = express();
  app.use(express.json({ limit: '256kb' }));
  app.use(rateLimitMiddleware(180));

  const auditRepo = new NodeSQLiteAuditRepository(customDbPath);
  const bridge = new PythonEngineBridge(auditRepo);
  const advisor = new ServerGeminiAdvisor();

  app.get('/health', (_req, res) => {
    res.json({
      status: bridge.getKillSwitchState().active
        ? 'halted'
        : bridge.isPythonConnected()
          ? 'ok'
          : 'degraded',
      trading_mode: bridge.getEffectiveMode(),
      python_engine_connected: bridge.isPythonConnected(),
      kill_switch_active: bridge.getKillSwitchState().active,
      timestamp_utc: Math.floor(Date.now() / 1000),
    });
  });

  app.use('/api', createApiRouter({ auditRepo, bridge, advisor }));

  return { app, auditRepo, bridge, advisor };
}
