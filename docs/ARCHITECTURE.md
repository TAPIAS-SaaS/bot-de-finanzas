# Arquitectura del Sistema (`ARCHITECTURE.md`)

## 1. Separación de Responsabilidades

El proyecto **Bot de Finanzas** divide estrictamente la interfaz de usuario, el servidor web de mediación y el motor cuantitativo en Python:

1. **Frontend React (`src/frontend/`)**:
   - Presenta el estado operativo real (`PAPER`, `DEMO` o `LIVE`), métricas contables en COP y USDT, curvas de patrimonio/drawdown y trazabilidad de decisiones.
   - Nunca invoca directamente a la API de Gemini ni a un exchange, y nunca almacena claves privadas.
2. **Servidor Node.js + Express (`server/` y `server.ts`)**:
   - Expone los endpoints autorizados (`/health`, `/api/status`, `/api/portfolio`, `/api/backtests`, `/api/risk`, `/api/ai/analysis`, etc.).
   - Ejecuta `ServerGeminiAdvisor` en el backend protegiendo `GEMINI_API_KEY`, aplicando límite de cuota horaria y validando el esquema JSON con **Zod**.
   - Se comunica con el motor cuantitativo Python (`PythonEngineBridge`) y comparte la base de datos de auditoría SQLite (`data/bot_finanzas.sqlite`).
3. **Motor Cuantitativo Python (`trading_engine/src/trading_bot/`)**:
   - Contiene la lógica determinista de validación de velas UTC (`data`), cálculo de indicadores (`indicators`), las 3 estrategias candidatas (`strategies`), el gestor de riesgo independiente (`risk`), el motor de backtesting 60/20/20 (`backtesting`), el adaptador experimental de TimesFM (`forecasting`) y la ejecución idempotente (`execution`).

## 2. Límites de Confianza y Comportamiento ante Fallos

- **Si el motor Python se desconecta**: El servidor cambia inmediatamente el modo efectivo a `DEMO` («Motor Python desconectado»), la interfaz muestra una advertencia visible y el `RiskManager` rechaza cualquier nueva entrada (`ENGINE_DISCONNECTED`).
- **Si Gemini falla, devuelve JSON malformado o agota su cuota**: `GeminiAdvisor` captura la excepción, registra la advertencia y devuelve una recomendación segura `HOLD` con `confidence: 0.0`. Nunca puede autorizar una orden.
- **Si TimesFM está deshabilitado o no tiene pesos locales montados**: `TimesFMForecastProvider` devuelve `available: false` sin inventar valores previstos, permitiendo que el motor arranque con normalidad y mostrando únicamente la línea base estadística claramente etiquetada.
- **Si el exchange sufre un timeout al enviar una orden**: `OrderExecutionEngine` marca la orden como `PENDING_RECONCILIATION` y bloquea cualquier nueva orden hasta consultar primero si la orden original fue creada en el exchange, evitando compras duplicadas.
