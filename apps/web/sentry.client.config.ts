import * as Sentry from "@sentry/nextjs";

const env = process.env.NEXT_PUBLIC_VERCEL_ENV ?? "development";
const isProd = env === "production";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: env,
  enabled: !!process.env.NEXT_PUBLIC_SENTRY_DSN,
  // 100% em dev/preview, 10% em produção.
  tracesSampleRate: isProd ? 0.1 : 1.0,
  beforeSend(event) {
    // Ruído típico de rede (offline, fetch abortado) — não acionável.
    const type = event.exception?.values?.[0]?.type;
    if (type === "NetworkError") return null;
    return event;
  },
});
