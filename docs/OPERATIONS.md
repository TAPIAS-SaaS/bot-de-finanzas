# Manual de Operaciones y Supervisión (`OPERATIONS.md`)

## 1. Supervisión Diaria en Modo Paper Trading

1. **Verificar el Indicador Superior de Modo**:
   - `[PAPER]`: Motor Python conectado y operando sobre base de datos SQLite local sin enviar órdenes reales.
   - `[DEMO]`: Motor Python desconectado; el sistema muestra datos de respaldo y bloquea cualquier nueva entrada.
   - `[LIVE]`: Órdenes reales (bloqueado por defecto).
2. **Revisar Métricas de Riesgo en la Vista Principal**:
   - Confirmar que el **Drawdown Actual** se mantenga por debajo de `-5,00%` y la **Pérdida Diaria** por debajo de `-1,00%`.
   - Verificar la marca de tiempo UTC de la última vela cerrada (`Última vela cerrada`). Si el desfase supera las 2 horas (`7200s`), el `RiskManager` rechaza automáticamente nuevas compras por `STALE_OR_FUTURE_DATA`.

## 2. Cómo Detener la Ejecución de Forma Segura

- **Pausa ordinaria de Paper Trading**: Haga clic en **«Pausar Paper Trading»** en la pestaña *Terminal Principal* (`POST /api/paper/pause`).
- **Parada inmediata de emergencia (*Kill Switch*)**: Haga clic en **«Interruptor de Emergencia»** en la barra superior (`POST /api/engine/pause`). Esto detiene inmediatamente nuevas decisiones de compra sin cerrar posiciones a ciegas mediante órdenes de mercado descontroladas.

## 3. Copia de Seguridad y Exportación de Auditoría

- Desde la pestaña **Auditoría SQLite**, utilice los botones **«Descargar CSV de Auditoría»** (`/api/export/csv`) o **«Descargar Informe Completo JSON»** (`/api/export/json`).
- Para realizar una copia de seguridad física del archivo SQLite en caliente:
  ```bash
  sqlite3 ./data/bot_finanzas.sqlite ".backup './data/backup_bot_finanzas.sqlite'"
  ```
- Nunca suba archivos `.sqlite` ni exportaciones de cuentas reales al repositorio público de GitHub.
