"use client";

import { trace, type Tracer } from "@opentelemetry/api";
import { ZoneContextManager } from "@opentelemetry/context-zone";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";
import { registerInstrumentations } from "@opentelemetry/instrumentation";
import { FetchInstrumentation } from "@opentelemetry/instrumentation-fetch";
import { Resource } from "@opentelemetry/resources";
import { SimpleSpanProcessor } from "@opentelemetry/sdk-trace-base";
import { WebTracerProvider } from "@opentelemetry/sdk-trace-web";

let started = false;
let tracer: Tracer | null = null;

/**
 * Inicializa OTel web exportando pro Logfire (OTLP/HTTP). No-op se o token
 * não estiver configurado — assim CI/preview sem token não quebram (a
 * propagação traceparent frontend→backend fica pra Fase 1, #risco 4).
 */
export function initTelemetry(): boolean {
  if (started || typeof window === "undefined") return started;
  const token = process.env.NEXT_PUBLIC_LOGFIRE_TOKEN;
  if (!token) return false;

  const provider = new WebTracerProvider({
    resource: new Resource({ "service.name": "uphiring-web" }),
    spanProcessors: [
      new SimpleSpanProcessor(
        new OTLPTraceExporter({
          url: "https://logfire-api.pydantic.dev/v1/traces",
          headers: { Authorization: `Bearer ${token}` },
        }),
      ),
    ],
  });
  provider.register({ contextManager: new ZoneContextManager() });
  registerInstrumentations({
    instrumentations: [
      new FetchInstrumentation({
        // NÃO propagar `traceparent` cross-origin. Com `[/.*/]` o header
        // ia em TODO fetch — inclusive pro endpoint de token do Clerk e
        // pro Logfire, cujo CORS rejeita o header → quebra a auth inteira
        // (Sprint risk #4). Default ([]) = sem propagação cross-origin;
        // stitching FE→BE fica pra Fase 1.
        ignoreUrls: [
          /clerk\.accounts\.dev/,
          /logfire-api\.pydantic\.dev/,
          /\.sentry\.io/,
          /\/monitoring/,
        ],
      }),
    ],
  });
  tracer = trace.getTracer("uphiring-web");
  started = true;
  return true;
}

/** Span curto para eventos discretos (page view, login). */
export function recordEvent(
  name: string,
  attributes: Record<string, string> = {},
): void {
  if (!tracer) return;
  const span = tracer.startSpan(name, { attributes });
  span.end();
}
