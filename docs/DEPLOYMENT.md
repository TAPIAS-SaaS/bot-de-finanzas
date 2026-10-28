# Guía de Despliegue (`DEPLOYMENT.md`)

## 1. Diferencia entre el Entorno de Google AI Studio y el Despliegue Productivo

- **En Google AI Studio Build**:
  - Se ejecuta el servidor Node.js (`server.ts`) en el puerto `3000`, sirviendo el Dashboard en React y las rutas protegidas de Express (`/api/*`).
  - El servidor Node.js invoca bajo demanda el paquete cuantitativo local en Python (`trading_engine/src/trading_bot`) para backtests y evaluaciones deterministas, persistiendo la auditoría en SQLite (`./data/bot_finanzas.sqlite`).
  - No debe asumirse que el contenedor de previsualización web mantenga procesos daemon de larga duración cuando no hay tráfico HTTP activo.

- **Despliegue Independiente del Motor Python (Docker o VPS Linux)**:
  Para ejecutar Paper Trading continuo durante 30 a 60 días las 24 horas:

```bash
cd trading_engine
docker build -t bot-de-finanzas-engine:1.0.0 .
docker run -d \
  --name bot-finanzas-paper \
  --restart unless-stopped \
  -p 127.0.0.1:8000:8000 \
  -v $(pwd)/../data:/app/data \
  -e TRADING_MODE=paper \
  -e ALLOW_LIVE_TRADING=false \
  bot-de-finanzas-engine:1.0.0
```

## 2. Requisitos Previos Antes de Considerar el Modo Real (`LIVE`)

El sistema bloqueará el arranque en modo `live` a menos que se cumplan las **12 condiciones verificadas por código**:
1. Ejecutar Paper Trading continuo durante al menos **30 a 60 días** y auditar cada operación frente al precio real de mercado.
2. Superar los criterios fuera de muestra (`OUT_OF_SAMPLE_APPROVED=true` con al menos 50 operaciones cerradas en la muestra OOS, rentabilidad neta positiva tras prueba de estrés de costes y `Profit Factor > 1.10`).
3. Verificar elegibilidad legal, mayoría de edad, residencia fiscal y KYC del titular de la cuenta en el exchange seleccionado (`ACCOUNT_ELIGIBILITY_VERIFIED=true`).
4. Configurar `TRADING_MODE=live`, `ALLOW_LIVE_TRADING=true` y `LIVE_TRADING_CONFIRMATION=ACEPTO_RIESGO_REAL_SPOT_SIN_GARANTIAS`.
