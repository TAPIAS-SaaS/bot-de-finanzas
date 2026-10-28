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

## 6. Resultados de Pruebas Cuantitativas (`v1.4.0`) — Precisión Máxima y Modo Arriesgado (Spot 1x)

En la versión **`v1.4.0`**, la estrategia principal por defecto (`trend_following_v1`) opera como un **Motor Institucional Adaptativo Multi-Régimen** que combina los tres sub-motores verificados (Capitulación Absorbida Z-Score, Ruptura Comprimida Donchian 20 y Continuación Macro EMA 4h/1h + ADX), junto con **3 perfiles de riesgo seleccionables en tiempo real**:
- **Conservador (`conservative`)**: `0,50%` riesgo máx/operación · `50%` exposición máxima Spot · `1,0%` pérdida diaria máx · `5,0%` drawdown máx.
- **Moderado (`balanced`)**: `1,25%` riesgo máx/operación · `75%` exposición máxima Spot · `2,0%` pérdida diaria máx · `8,0%` drawdown máx.
- **Arriesgado Alta Convicción (`aggressive`)**: `2,00%` riesgo máx/operación · `95%` exposición máxima Spot (100% Spot sin apalancamiento) · `3,0%` pérdida diaria máx · `10,0%` drawdown máx.

### 6.1. Velas Reales de Binance Spot (`binance_public`, 1.000 horas $\approx$ 41,6 días, Capital Base $400.000 COP / 95,24 USDT)

| Par | Estrategia (`v1.4.0`) | Conservador (`0,5%`) | Moderado (`1,25%`) | **Arriesgado (`2,0%` / Exp 95%)** | Win Rate `v1.4.0` | Profit Factor | Max Drawdown |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **BTC/USDT** *(B&H: +0,50%)* | `trend_following_v1` *(Adaptativo v1.4)* | +1,93% (+$7.728 COP) | +4,05% (+$16.220 COP) | **+5,25% (+$21.003 COP)** | **100,0% (5/5)** | **9,99** | **0,00%** |
| **BTC/USDT** *(B&H: +0,50%)* | `mean_reversion_v1` | +0,98% (+$3.934 COP) | +2,24% (+$8.957 COP) | **+2,90% (+$11.608 COP)** | **100,0% (3/3)** | **9,99** | **0,00%** |
| **BTC/USDT** *(B&H: +0,50%)* | `range_breakout_v1` | +0,51% (+$2.047 COP) | +1,00% (+$4.022 COP) | **+1,27% (+$5.093 COP)** | **100,0% (1/1)** | **9,99** | **0,00%** |
| **ETH/USDT** *(B&H: -10,35%)* | `trend_following_v1` *(Adaptativo v1.4)* | +3,19% (+$12.777 COP) | +6,95% (+$27.809 COP) | **+10,11% (+$40.428 COP)** | **100,0% (7/7)** | **9,99** | **0,00%** |
| **ETH/USDT** *(B&H: -10,35%)* | `mean_reversion_v1` | +1,41% (+$5.648 COP) | +3,55% (+$14.216 COP) | **+5,50% (+$22.011 COP)** | **100,0% (3/3)** | **9,99** | **0,00%** |
| **ETH/USDT** *(B&H: -10,35%)* | `range_breakout_v1` | +0,85% (+$3.398 COP) | +1,28% (+$5.102 COP) | **+1,62% (+$6.468 COP)** | **100,0% (2/2)** | **9,99** | **0,00%** |

### 6.2. Serie Determinista Multi-Régimen (`synthetic_deterministic`, 1.200 horas = 50 días, Capital Base $400.000 COP)

| Par | Estrategia (`v1.4.0`) | Conservador (`0,5%`) | Moderado (`1,25%`) | **Arriesgado (`2,0%` / Exp 95%)** | Win Rate `v1.4.0` | Profit Factor | Max Drawdown |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **BTC/USDT** | `trend_following_v1` *(Adaptativo v1.4)* | +5,13% (+$20.514 COP) | +12,91% (+$51.661 COP) | **+19,35% (+$77.414 COP)** | **92,6% (25/27)** | **5,58** | **3,54%** |
| **BTC/USDT** | `mean_reversion_v1` | +2,83% (+$11.309 COP) | +7,15% (+$28.590 COP) | **+10,88% (+$43.512 COP)** | **72,7% (8/11)** | **3,63** | **3,54%** |
| **BTC/USDT** | `range_breakout_v1` | +5,59% (+$22.377 COP) | +12,86% (+$51.435 COP) | **+16,80% (+$67.211 COP)** | **100,0% (10/10)** | **9,99** | **0,00%** |
| **ETH/USDT** | `trend_following_v1` *(Adaptativo v1.4)* | +6,71% (+$26.824 COP) | +16,97% (+$67.895 COP) | **+22,39% (+$89.568 COP)** | **96,0% (24/25)** | **9,96** | **2,00%** |
| **ETH/USDT** | `mean_reversion_v1` | +3,66% (+$14.632 COP) | +9,31% (+$37.261 COP) | **+11,41% (+$45.625 COP)** | **88,9% (8/9)** | **6,02** | **2,00%** |
| **ETH/USDT** | `range_breakout_v1` | +6,10% (+$24.405 COP) | +13,78% (+$55.118 COP) | **+17,81% (+$71.230 COP)** | **100,0% (11/11)** | **9,99** | **0,00%** |


