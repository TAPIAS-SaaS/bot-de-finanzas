/**
 * Servicio `GeminiAdvisor` en el servidor Node.js.
 *
 * Cumple las directrices del skill `gemini-api` y la sección 9 del Prompt Maestro:
 * - Utiliza `@google/genai` exclusivamente desde el servidor.
 * - Modelo configurable por defecto: `gemini-3.8-flash`.
 * - Cabecera `User-Agent: 'aistudio-build'`.
 * - Esquema JSON estructurado y validado con Zod.
 * - Control de cuota horaria y fallback seguro (`HOLD`) si no hay clave configurada o falla la red.
 * - Nunca tiene acceso a ejecución de órdenes, retiros ni credenciales del exchange.
 */

import { GoogleGenAI, Type } from '@google/genai';
import { z } from 'zod';
import type { AdvisorAnalysisDTO } from '../../src/shared/types';

const ALLOWED_STRATEGIES = [
  'trend_following_v1',
  'mean_reversion_v1',
  'range_breakout_v1',
] as const;

export const AdvisorResponseZodSchema = z.object({
  market_regime: z.enum(['TRENDING', 'MEAN_REVERTING', 'RANGING', 'VOLATILE', 'UNCERTAIN']),
  recommendation: z.enum(['BUY', 'SELL', 'HOLD', 'PAUSE']),
  confidence: z.number().min(0).max(1),
  supporting_factors: z.array(z.string()).max(8),
  risk_factors: z.array(z.string()).max(8),
  strategy_id: z.enum(ALLOWED_STRATEGIES).nullable(),
  reason: z.string().min(1).max(1200),
  data_timestamp: z.string(),
  model_id: z.string(),
  warnings: z.array(z.string()),
});

export class ServerGeminiAdvisor {
  private callTimestamps: number[] = [];
  private readonly maxCallsPerHour: number;
  private readonly modelId: string;

  constructor() {
    this.maxCallsPerHour = Number(process.env.GEMINI_MAX_CALLS_PER_HOUR || 15);
    this.modelId = process.env.GEMINI_MODEL || 'gemini-3.8-flash';
  }

  private checkQuota(): boolean {
    const oneHourAgo = Date.now() - 3600_000;
    this.callTimestamps = this.callTimestamps.filter((t) => t > oneHourAgo);
    return this.callTimestamps.length < this.maxCallsPerHour;
  }

  public async analyzeMarketContext(context: {
    symbol: string;
    referencePrice: number;
    indicators: Record<string, number>;
    lastSignal: string;
    activeStrategyId: string;
    dataTimestamp: number;
  }): Promise<AdvisorAnalysisDTO> {
    const isoTs = new Date(context.dataTimestamp * 1000).toISOString();
    const apiKey = process.env.GEMINI_API_KEY?.trim();

    if (!apiKey || apiKey === 'MY_GEMINI_API_KEY') {
      return this.buildSafeFallback(
        context,
        isoTs,
        'Clave GEMINI_API_KEY no configurada en el entorno; operando con análisis determinista local.'
      );
    }

    if (!this.checkQuota()) {
      return this.buildSafeFallback(
        context,
        isoTs,
        `Límite horario de llamadas a Gemini alcanzado (${this.maxCallsPerHour}/h). Se recomienda HOLD.`
      );
    }

    try {
      this.callTimestamps.push(Date.now());
      const ai = new GoogleGenAI({
        apiKey,
        httpOptions: {
          headers: {
            'User-Agent': 'aistudio-build',
          },
        },
      });

      const prompt = `Analiza de forma objetiva y prudente el siguiente resumen técnico del par cripto spot ${context.symbol} (sin apalancamiento):
- Precio de cierre 1h: ${context.referencePrice} USDT
- Timestamp UTC de la vela cerrada: ${isoTs}
- Estrategia activa: ${context.activeStrategyId}
- Última señal determinista: ${context.lastSignal}
- Indicadores calculados sobre velas cerradas: ${JSON.stringify(context.indicators)}

Reglas obligatorias:
1. No prometas ganancias ni afirmes certezas.
2. Solo puedes sugerir estrategias de la lista permitida: trend_following_v1, mean_reversion_v1, range_breakout_v1, o null.
3. Si los indicadores son mixtos o el coste/riesgo es desfavorable, recomienda HOLD o PAUSE.
4. Responde en español claro y técnico.`;

      const response = await ai.models.generateContent({
        model: this.modelId,
        contents: prompt,
        config: {
          systemInstruction:
            'Eres un analista cuantitativo de riesgo conservador. Nunca autorizas órdenes por tu cuenta ni modificas límites del gestor de riesgo. Devuelve exclusivamente el JSON estructurado.',
          temperature: 0.2,
          responseMimeType: 'application/json',
          responseSchema: {
            type: Type.OBJECT,
            properties: {
              market_regime: {
                type: Type.STRING,
                description: 'TRENDING, MEAN_REVERTING, RANGING, VOLATILE o UNCERTAIN',
              },
              recommendation: {
                type: Type.STRING,
                description: 'BUY, SELL, HOLD o PAUSE',
              },
              confidence: {
                type: Type.NUMBER,
                description: 'Valor entre 0.0 y 1.0 (no calibrado como probabilidad de ganancia)',
              },
              supporting_factors: {
                type: Type.ARRAY,
                items: { type: Type.STRING },
              },
              risk_factors: {
                type: Type.ARRAY,
                items: { type: Type.STRING },
              },
              strategy_id: {
                type: Type.STRING,
                nullable: true,
              },
              reason: {
                type: Type.STRING,
              },
            },
            required: [
              'market_regime',
              'recommendation',
              'confidence',
              'supporting_factors',
              'risk_factors',
              'reason',
            ],
          },
        },
      });

      const rawText = response.text?.trim() || '{}';
      const parsedJson = JSON.parse(rawText);
      const candidate = {
        ...parsedJson,
        strategy_id: ALLOWED_STRATEGIES.includes(parsedJson.strategy_id)
          ? parsedJson.strategy_id
          : null,
        data_timestamp: isoTs,
        model_id: this.modelId,
        warnings: [
          'La puntuación de confianza es heurística y no constituye probabilidad calibrada de ganancia.',
          'Toda orden requiere aprobación determinista del RiskManager.',
        ],
      };

      const validated = AdvisorResponseZodSchema.parse(candidate);
      return {
        ...validated,
        source: 'gemini_live_api',
      };
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Error desconocido al invocar Gemini';
      return this.buildSafeFallback(
        context,
        isoTs,
        `Fallo o rechazo de validación en llamada a Gemini (${msg.slice(0, 120)}). Se mantiene HOLD.`
      );
    }
  }

  public buildSafeFallback(
    context: {
      symbol: string;
      referencePrice: number;
      indicators: Record<string, number>;
      lastSignal: string;
      activeStrategyId: string;
    },
    isoTs: string,
    warningReason: string
  ): AdvisorAnalysisDTO {
    const ema50_4h = context.indicators.ema50_4h ?? 0;
    const ema200_4h = context.indicators.ema200_4h ?? 0;
    const atr = context.indicators.atr14_1h ?? 0;
    const isTrending = ema50_4h > 0 && ema200_4h > 0 && ema50_4h > ema200_4h;

    return {
      market_regime: isTrending ? 'TRENDING' : 'RANGING',
      recommendation: 'HOLD',
      confidence: 0.0,
      supporting_factors: [
        `Precio de referencia cerrado en ${context.referencePrice.toLocaleString('es-CO')} USDT (${context.symbol}).`,
        ema50_4h > 0
          ? `Filtro macro 4h: EMA50 (${ema50_4h.toFixed(1)}) vs EMA200 (${ema200_4h.toFixed(1)}).`
          : 'Indicadores evaluados exclusivamente sobre velas cerradas.',
      ],
      risk_factors: [
        warningReason,
        atr > 0
          ? `Volatilidad ATR(14) actual: ${atr.toFixed(2)} USDT por hora.`
          : 'Sujeto a límites de riesgo de 0,5% por operación y 5% de drawdown máximo.',
      ],
      strategy_id: context.activeStrategyId as AdvisorAnalysisDTO['strategy_id'],
      reason:
        'Evaluación preventiva en modo conservador (HOLD). El asesor IA es informativo y nunca anula las reglas del Gestor de Riesgo.',
      data_timestamp: isoTs,
      model_id: this.modelId,
      warnings: [
        warningReason,
        'La explicación del asesor no constituye prueba de rentabilidad ni autorización de orden.',
      ],
      source: 'deterministic_fallback',
    };
  }
}
