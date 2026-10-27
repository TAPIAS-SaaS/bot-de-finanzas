/**
 * Funciones puras de formato financiero, etiquetas de modo y validación para el Frontend.
 * Desacopladas del DOM para pruebas unitarias deterministas con `node:test`.
 */

import type { TradingMode } from '../../shared/types';

export function formatCop(amount: number): string {
  const rounded = Math.round(amount);
  const sign = rounded < 0 ? '-' : '';
  const absStr = Math.abs(rounded)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return `${sign}$${absStr} COP`;
}

export function formatUsdt(amount: number, decimals = 2): string {
  const sign = amount < 0 ? '-' : '';
  return `${sign}${Math.abs(amount).toFixed(decimals)} USDT`;
}

export function formatSignedPct(pct: number, decimals = 2): string {
  const sign = pct > 0 ? '+' : '';
  return `${sign}${pct.toFixed(decimals)}%`;
}

export function formatUtcTimestamp(tsSeconds: number): string {
  if (!tsSeconds || tsSeconds <= 0) return 'Sin datos UTC';
  const d = new Date(tsSeconds * 1000);
  return d.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
}

export function getModeDescriptor(mode: TradingMode, pythonConnected: boolean): {
  code: 'DEMO' | 'PAPER' | 'LIVE';
  title: string;
  subtitle: string;
  warningText: string;
} {
  if (mode === 'live') {
    return {
      code: 'LIVE',
      title: 'LIVE — Órdenes Reales Spot',
      subtitle: 'Ejecución real sobre cuenta del exchange sin apalancamiento.',
      warningText:
        'ADVERTENCIA CRÍTICA: El modo LIVE opera con capital real. Ninguna estrategia garantiza beneficios futuros.',
    };
  }
  if (mode === 'demo' || !pythonConnected) {
    return {
      code: 'DEMO',
      title: 'DEMO — Motor Python Desconectado',
      subtitle: 'Visualización de respaldo auditable. Nuevas órdenes bloqueadas.',
      warningText:
        'Motor cuantitativo Python desconectado: el sistema rechaza nuevas entradas y muestra exclusivamente resultados de referencia previamente verificados.',
    };
  }
  return {
    code: 'PAPER',
    title: 'PAPER — Operaciones Virtuales en Simulación',
    subtitle: 'Simulación determinista conectada a SQLite sin envío de órdenes reales.',
    warningText:
      'Modo seguro por defecto (PAPER): ninguna orden real es enviada al exchange. Capital de referencia: $400.000 COP.',
  };
}
