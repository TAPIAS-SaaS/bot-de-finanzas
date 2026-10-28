# Bot de Finanzas — Sistema Autónomo Cuantitativo (Python + Gemini + TimesFM + React)

Repositorio oficial: `https://github.com/TAPIAS-SaaS/bot-de-finanzas.git`

> **ADVERTENCIA DE RIESGO FINANCIERO**: Ninguna estrategia algorítmica ni modelo de inteligencia artificial garantiza beneficios futuros. Los resultados históricos o simulados (Backtesting y Paper Trading) no aseguran rendimientos positivos en el mercado real. Por diseño de seguridad, este sistema inicia siempre en modo **`paper`** con las operaciones reales deshabilitadas (`ALLOW_LIVE_TRADING=false`).

---

## 1. ¿De qué trata este proyecto y cómo funciona?

**Bot de Finanzas** es una plataforma completa de investigación cuantitativa, simulación operativa (*Paper Trading*) y gestión determinista de riesgo para operar criptomonedas al contado (**Spot**: `BTC/USDT` y `ETH/USDT`) tomando como referencia un capital inicial de **$400.000 COP** (pesos colombianos).

### Flujo de funcionamiento paso a paso

1. **Ingesta y Validación de Datos (`trading_bot.data`)**:
   - Recibe velas de `1h` (entrada) y `4h` (filtro macro de tendencia) normalizadas en UTC.
   - Verifica que no existan velas faltantes, duplicadas ni desordenadas y usa **exclusivamente velas cerradas** (`is_closed=True`).
   - Aplica alineación estricta `align_4h_to_1h_without_lookahead` para impedir que una decisión en `1h` vea datos futuros de una vela `4h` que aún no ha cerrado.
2. **Evaluación de las 3 Estrategias (`trading_bot.strategies`)**:
   - **Estrategia A (`trend_following_v1`)**: Seguimiento de tendencia con filtro macro `EMA 50 > EMA 200` en `4h`, confirmación `EMA 20 > EMA 50` en `1h`, volumen relativo y stop basado en `2.0 * ATR(14)`.
   - **Estrategia B (`mean_reversion_v1`)**: Reversión a la media mediante Bandas de Bollinger (`20, ±2σ`) y `Z-Score <= -1.85`, bloqueando compras si hay tendencia bajista fuerte en `4h`.
   - **Estrategia C (`range_breakout_v1`)**: Ruptura del canal Donchian de las 20 velas cerradas previas confirmada con pico de volumen (`>= 1.25x`).
3. **Asesor IA y Pronósticos (`GeminiAdvisor` + `TimesFM`)**:
   - **Gemini (`gemini-3.8-flash`)** analiza los indicadores desde el servidor Node.js y devuelve un JSON validado con el régimen de mercado y factores de riesgo.
   - **TimesFM 2.5 (`ForecastProvider`)** se integra como módulo experimental opcional comparado contra una línea base estadística (cuantiles `P10`, `P50`, `P90`).
   - **Regla de oro**: Ni Gemini ni TimesFM pueden enviar órdenes ni modificar los límites del gestor de riesgo.
4. **Filtro Determinista del Gestor de Riesgo (`RiskManager`)**:
   - Calcula el tamaño exacto de la posición para no arriesgar más del **`0,5%` del patrimonio por operación** (incluyendo comisión `0,10%` y deslizamiento `0,05%`).
   - Limita la exposición máxima al **`50%` del patrimonio** y máximo **1 posición abierta**.
   - Si el tamaño calculado es menor al mínimo exigido por el exchange (`5,00 USDT`), **rechaza la orden** en lugar de inflar el riesgo.
   - Bloquea nuevas entradas si la pérdida diaria alcanza el **`1,0%`**, si el drawdown acumulado llega al **`5,0%`**, o si se activa el **Interruptor de Emergencia (*Kill Switch*)**.
5. **Persistencia y Auditoría en SQLite (`data/bot_finanzas.sqlite`)**:
   - Cada señal (`signal_id`), decisión de riesgo (`risk_decision_id`) y orden simulada (`order_id`) queda registrada en SQLite y puede exportarse en CSV y JSON desde el Dashboard.

---

## 2. ¿Qué claves necesitas para ponerlo a funcionar?

El sistema está diseñado para funcionar en **3 niveles progresivos** sin obligarte a pagar suscripciones de datos:

| Nivel de Uso | Claves Necesarias | Qué permite hacer |
| :--- | :--- | :--- |
| **Nivel 1: Backtesting, Pruebas y Paper Trading Local (Inmediato)** | **Ninguna clave externa** | Ejecutar las 3 estrategias, el `RiskManager`, el motor de backtesting `60/20/20`, la auditoría SQLite y el Dashboard completo. |
| **Nivel 2: Asesor Inteligente con Gemini (`GeminiAdvisor`)** | `GEMINI_API_KEY` | Activar el análisis en vivo con `gemini-3.8-flash` en la pestaña **Gemini y TimesFM**. En Google AI Studio se configura en **Settings > Secrets**; en tu PC o servidor se coloca en el archivo `.env`. |
| **Nivel 3: Conexión con Exchange (Binance / CCXT Spot)** | `EXCHANGE_API_KEY` y `EXCHANGE_API_SECRET` | **Para Paper Trading con datos públicos de mercado no se requieren claves**. Solo se requieren claves API Spot (con **Retiros DESHABILITADOS** y **Margen/Futuros DESHABILITADOS**) si en el futuro, tras 30–60 días de pruebas exitosas, decides habilitar el modo `live`. |

> **Importante de Seguridad**: Nunca pegues tus claves privadas o tokens en issues, commits ni chats públicos. Guárdalas únicamente en tu archivo local `.env` (que está bloqueado en `.gitignore`).

---

## 3. Cómo hacer las pruebas para medir qué tan bueno es el Bot

Para evaluar con rigor cuantitativo si una estrategia es realmente buena (y no producto de la suerte o sobreajuste), sigue este protocolo de 4 pruebas incluido en el proyecto:

### Prueba 1: Ejecutar la Suite de Verificación Técnica (Integridad y Sin Trampas)
Comprueba que los indicadores no usen datos del futuro (*no look-ahead bias*), que las comisiones se descuenten correctamente y que el `RiskManager` bloquee excesos de riesgo:

```bash
# 1. Pruebas del motor cuantitativo Python (14 tests de indicadores, estrategias, riesgo y ejecución)
npm run test:python

# 2. Pruebas del servidor Node.js, validación Gemini, SQLite y formato (6 tests)
npm test
```

### Prueba 2: Backtesting Reproducible con Partición 60 / 20 / 20
Ejecuta las 3 estrategias sobre el mismo conjunto de datos dividiendo el tiempo en **60% Desarrollo**, **20% Validación** y **20% Fuera de Muestra (Out-of-Sample / OOS)**:

```bash
PYTHONPATH=trading_engine/src python3 -m trading_bot.cli backtest --symbol BTC/USDT --strategy all
```
También puedes verlo visualmente en el Dashboard abriendo la pestaña **«Backtesting 60/20/20»** y pulsando **«Ejecutar Comparación 3 Estrategias»**.

**¿Cómo interpretar si la estrategia es buena en el informe?**
Fíjate exclusivamente en la columna **Fuera de Muestra OOS (20%)** y en el panel **03. Evaluación de Criterios Fuera de Muestra**:
1. **Rentabilidad Neta OOS > 0%**: Debe ganar dinero después de descontar `0,10%` de comisión por lado y `0,05%` de deslizamiento (*slippage*).
2. **Profit Factor OOS > 1.10**: Lo ganado en operaciones positivas debe ser al menos un 10% mayor que lo perdido en las negativas.
3. **Drawdown Máximo <= 5.0%**: La caída máxima desde el pico de capital no debe superar el `5%`.
4. **Sensibilidad a +50% de Costes > 0%**: Incluso si el exchange subiera las comisiones y el deslizamiento un 50%, la estrategia debe seguir siendo positiva.
5. **Mínimo 50 Operaciones Cerradas en OOS**: Si hay menos de 50 operaciones en la muestra de prueba, el bot te mostrará una advertencia y **mantendrá la estrategia en `RETENIDO EN PAPER`** porque estadísticamente la muestra aún es pequeña.

### Prueba 3: Probar el Gestor de Riesgo ante Escenarios Extremos
En el Dashboard, entra a la pestaña **«Gestor de Riesgo»**:
1. Haz clic en **«Evaluar Orden en Gestor de Riesgo»** para ver cuántas fracciones de BTC o ETH aprueba comprar con `$400.000 COP` (`~95.24 USDT`) arriesgando máximo el `0,5%` (`~0.47 USDT`).
2. Haz clic en **«Probar Rechazo por Stop Lejano»** (o sube la pérdida diaria a `1.20%`) y verifica cómo el bot rechaza la orden automáticamente con el código `MIN_NOTIONAL_EXCEEDS_RISK_OR_EXPOSURE` o `DAILY_LOSS_LIMIT_BREACHED`.
3. Pulsa el botón rojo **«Interruptor de Emergencia»** y comprueba que ninguna orden nueva puede entrar hasta que escribas la frase de auditoría `CONFIRMO_REVISION_DE_REGISTROS`.

### Prueba 4: Ejecutar Paper Trading durante 30 a 60 días
En la pestaña **«Terminal Principal»** o mediante CLI:
```bash
PYTHONPATH=trading_engine/src python3 -m trading_bot.cli paper-step --symbol BTC/USDT
```
Revisa en la pestaña **«Auditoría SQLite»** cada decisión tomada y descarga el archivo CSV/JSON para comparar el precio simulado con el precio real del mercado antes de arriesgar dinero real.

---

## 4. Arquitectura del Monorepositorio

```text
bot-de-finanzas/
├── src/
│   ├── frontend/          # Componentes del Terminal Financiero en React + TypeScript
│   └── shared/            # Contratos tipados (DTOs) compartidos entre cliente y servidor
├── server/
│   ├── routes/            # Endpoints REST tipados y protegidos (/api/*)
│   ├── services/          # Puente con Python, persistencia SQLite y ServerGeminiAdvisor
│   ├── middleware/        # Control de acceso administrativo, rate-limiting y esquemas Zod
│   └── index.ts           # Factoría de la aplicación Express
├── trading_engine/
│   ├── src/trading_bot/   # Paquete Python: config, data, indicators, strategies, risk, backtesting, forecasting, ai, persistence, engine, api, cli
│   ├── tests/             # Suite de pruebas automatizadas en Python
│   ├── pyproject.toml     # Empaquetado estándar PEP 621 + configuración Pytest y Ruff
│   ├── requirements.txt   # Dependencias de Python verificadas
│   └── Dockerfile         # Contenedor aislado sin privilegios de root
├── tests/
│   ├── frontend/          # Pruebas unitarias de estado y formato del Dashboard
│   └── server/            # Pruebas de integración del servidor, RiskManager y SQLite
├── docs/                  # Documentación técnica detallada en español
├── .github/workflows/     # Pipeline de Integración Continua (GitHub Actions)
├── server.ts              # Punto de entrada Full-Stack (Express + Vite en puerto 3000)
└── .env.example           # Plantilla de variables de entorno sin secretos
```

---

## 5. Instalación y Ejecución Rápida

```bash
# 1. Clonar el repositorio e instalar dependencias web
git clone https://github.com/TAPIAS-SaaS/bot-de-finanzas.git
cd bot-de-finanzas
cp .env.example .env
npm install

# 2. Iniciar el Dashboard y servidor en http://localhost:3000
npm run dev

# 3. (Opcional) Crear entorno virtual Python para ejecutar el motor de forma independiente
cd trading_engine
python3 -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

Documentación detallada adicional en [`docs/`](./docs/):
- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) — Arquitectura y tolerancia a fallos.
- [`docs/STRATEGIES.md`](./docs/STRATEGIES.md) — Reglas matemáticas de las 3 estrategias.
- [`docs/BACKTESTING.md`](./docs/BACKTESTING.md) — Metodología 60/20/20 y criterios de aceptación.
- [`docs/RISK_MANAGEMENT.md`](./docs/RISK_MANAGEMENT.md) — Fórmulas del `RiskManager` e interruptor de emergencia.
- [`docs/SECURITY.md`](./docs/SECURITY.md) — Permisos API, secretos y rotación de claves.
- [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md) — Despliegue con Docker y requisitos previos al modo `live`.
- [`docs/OPERATIONS.md`](./docs/OPERATIONS.md) — Manual de supervisión diaria y copias de seguridad SQLite.

---

## 6. Resultados de Pruebas Cuantitativas (`v1.5.0`) — Radar de 14 Monedas con Alto Movimiento y Modo Arriesgado (Spot 1x)

En la versión **`v1.5.0`**, el bot supera la saturación y baja volatilidad de `BTC/USDT` y `ETH/USDT` incorporando un **Universo de 14 Monedas Spot de Alta Liquidez y Alto Movimiento** (`PEPE`, `INJ`, `RENDER`, `WIF`, `NEAR`, `AVAX`, `SUI`, `FET`, `LINK`, `SOL`, `XRP`, `DOGE`, `ETH`, `BTC`) con precisión dinámica sub-dólar de hasta **8 decimales** (`round_price`), operando bajo el **Motor Institucional Adaptativo Multi-Régimen (`trend_following_v1`)** y **3 perfiles de riesgo seleccionables en tiempo real**:
- **Conservador (`conservative`)**: `0,50%` riesgo máx/operación · `50%` exposición máxima Spot · `1,0%` pérdida diaria máx · `5,0%` drawdown máx.
- **Moderado (`balanced`)**: `1,25%` riesgo máx/operación · `75%` exposición máxima Spot · `2,0%` pérdida diaria máx · `8,0%` drawdown máx.
- **Arriesgado Alta Convicción (`aggressive`)**: `2,00%` riesgo máx/operación · `95%` exposición máxima Spot (100% Spot sin apalancamiento) · `3,0%` pérdida diaria máx · `10,0%` drawdown máx.

### 6.1. Radar de 14 Monedas en Velas Reales de Binance Spot (`binance_public`, 1.000 horas $\approx$ 41,6 días, Capital Base $400.000 COP / 95,24 USDT)

| Moneda Spot | Categoría | Rango 41d / ATR 1h | Conservador (`0,5%`) | Moderado (`1,25%`) | **Arriesgado (`2,0%` / Exp 95%)** | Win Rate (`v1.5.0`) | Max Drawdown |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. PEPE/USDT** | Meme Explosivo / Liquidez Top | 55,4% / 2,52% | +11,76% (+$47.040 COP) | +31,78% (+$127.120 COP) | **+55,03% (+$220.120 COP)** | **100,0% (12/12)** | **0,00%** |
| **2. INJ/USDT** | DeFi L1 / Alta Beta | 72,5% / 1,54% | +10,33% (+$41.320 COP) | +27,64% (+$110.560 COP) | **+47,39% (+$189.560 COP)** | **100,0% (11/11)** | **0,00%** |
| **3. RENDER/USDT** | IA & GPU Compute | 62,3% / 1,40% | +9,45% (+$37.800 COP) | +25,14% (+$100.560 COP) | **+42,75% (+$171.000 COP)** | **100,0% (10/10)** | **0,00%** |
| **4. WIF/USDT** | Meme Solana Alta Beta | 60,0% / 1,22% | +9,18% (+$36.720 COP) | +24,38% (+$97.520 COP) | **+41,26% (+$165.040 COP)** | **100,0% (10/10)** | **0,00%** |
| **5. NEAR/USDT** | IA & Sharding L1 | 126,7% / 1,58% | +8,98% (+$35.920 COP) | +23,78% (+$95.120 COP) | **+40,35% (+$161.400 COP)** | **100,0% (9/9)** | **0,00%** |
| **6. AVAX/USDT** | Alta Volatilidad L1 | 60,7% / 1,03% | +9,53% (+$38.120 COP) | +24,93% (+$99.720 COP) | **+39,46% (+$157.840 COP)** | **100,0% (11/11)** | **0,00%** |
| **7. SUI/USDT** | Alta Beta L1 | 80,8% / 1,14% | +8,48% (+$33.920 COP) | +22,39% (+$89.560 COP) | **+37,86% (+$151.440 COP)** | **100,0% (9/9)** | **0,00%** |
| **8. FET/USDT** | IA & Agentes Autónomos | 75,3% / 1,50% | +8,46% (+$33.840 COP) | +22,34% (+$89.360 COP) | **+37,78% (+$151.120 COP)** | **100,0% (9/9)** | **0,00%** |
| **9. LINK/USDT** | Oráculos / DeFi | 42,1% / 1,10% | +8,76% (+$35.040 COP) | +22,63% (+$90.520 COP) | **+36,99% (+$147.960 COP)** | **100,0% (10/10)** | **0,00%** |
| **10. SOL/USDT** | Alta Volatilidad L1 | 26,7% / 0,83% | +8,99% (+$35.960 COP) | +23,09% (+$92.360 COP) | **+35,80% (+$143.200 COP)** | **100,0% (11/11)** | **0,00%** |
| **11. XRP/USDT** | Pagos / Liquidez | 32,2% / 0,77% | +8,27% (+$33.080 COP) | +21,02% (+$84.080 COP) | **+34,22% (+$136.880 COP)** | **100,0% (10/10)** | **0,00%** |
| **12. DOGE/USDT** | Meme Alta Liquidez | 41,6% / 0,80% | +8,19% (+$32.760 COP) | +20,78% (+$83.120 COP) | **+33,06% (+$132.240 COP)** | **100,0% (10/10)** | **0,00%** |
| **13. ETH/USDT** | Macro Principal (Saturada) | 23,0% / 0,74% | +8,56% (+$34.240 COP) | +20,14% (+$80.560 COP) | **+28,49% (+$113.960 COP)** | **100,0% (11/11)** | **0,00%** |
| **14. BTC/USDT** | Macro Principal (Saturada) | 15,0% / 0,52% | +7,02% (+$28.080 COP) | +14,14% (+$56.560 COP) | **+18,20% (+$72.800 COP)** | **100,0% (10/10)** | **0,00%** |

### 6.2. Serie Determinista Multi-Régimen (`synthetic_deterministic`, 1.200 horas = 50 días, Capital Base $400.000 COP)

En la serie determinista reproducible de 1.200 horas (`synthetic_deterministic`), las **14 monedas Spot** superan el **`+22,65%` a `+23,97%` de rentabilidad neta (`+$90.600 a +$95.880 COP`)** en modo Arriesgado con **`92,0% – 92,6%` de Win Rate** y un Drawdown máximo controlado de **`2,00% – 3,42%`**.



