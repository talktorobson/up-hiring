import * as Sentry from "@sentry/nextjs";

const env = process.env.VERCEL_ENV ?? "development";
const isProd = env === "production";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: env,
  enabled: !!process.env.NEXT_PUBLIC_SENTRY_DSN,
  tracesSampleRate: isProd ? 0.1 : 1.0,
  beforeSend(event) {
    const type = event.exception?.values?.[0]?.type;
    if (type === "NetworkError") return null;
    return event;
  },
});
