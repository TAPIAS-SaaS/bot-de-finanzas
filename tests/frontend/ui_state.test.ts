import test from 'node:test';
import assert from 'node:assert/strict';
import {
  formatCop,
  formatSignedPct,
  formatUsdt,
  formatUtcTimestamp,
  getModeDescriptor,
} from '../../src/frontend/utils/formatters';

test('formatCop y formatUsdt formatean correctamente capital de referencia de 400.000 COP', () => {
  assert.equal(formatCop(400000), '$400.000 COP');
  assert.equal(formatCop(-12500), '-$12.500 COP');
  assert.equal(formatUsdt(95.2381, 2), '95.24 USDT');
  assert.equal(formatSignedPct(2.456, 2), '+2.46%');
  assert.equal(formatSignedPct(-1.2, 2), '-1.20%');
});

test('getModeDescriptor distingue explícitamente entre DEMO, PAPER y LIVE', () => {
  const paperDesc = getModeDescriptor('paper', true);
  assert.equal(paperDesc.code, 'PAPER');

  const disconnectedDesc = getModeDescriptor('paper', false);
  assert.equal(disconnectedDesc.code, 'DEMO');
  assert.equal(disconnectedDesc.title.includes('Desconectado'), true);

  const liveDesc = getModeDescriptor('live', true);
  assert.equal(liveDesc.code, 'LIVE');
  assert.equal(liveDesc.warningText.includes('ADVERTENCIA CRÍTICA'), true);
});

test('formatUtcTimestamp normaliza marcas de tiempo en UTC legible', () => {
  assert.equal(formatUtcTimestamp(1_767_225_600), '2026-01-01 00:00:00 UTC');
  assert.equal(formatUtcTimestamp(0), 'Sin datos UTC');
});
