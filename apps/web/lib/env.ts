import { z } from "zod";

/**
 * Env é validado em boot. Vars `NEXT_PUBLIC_*` precisam ser referenciadas
 * literalmente (não via `process.env[x]`) senão o Next não inlina no bundle
 * client. `CLERK_SECRET_KEY` só existe no server — valida condicionalmente.
 */
const clientSchema = z.object({
  NEXT_PUBLIC_API_URL: z.string().url(),
  NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: z.string().min(1),
  NEXT_PUBLIC_CLERK_SIGN_IN_URL: z.string().default("/sign-in"),
  NEXT_PUBLIC_CLERK_SIGN_UP_URL: z.string().default("/sign-up"),
});

const clientValues = {
  NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY,
  NEXT_PUBLIC_CLERK_SIGN_IN_URL: process.env.NEXT_PUBLIC_CLERK_SIGN_IN_URL,
  NEXT_PUBLIC_CLERK_SIGN_UP_URL: process.env.NEXT_PUBLIC_CLERK_SIGN_UP_URL,
};

function fail(prefix: string, error: z.ZodError): never {
  const lines = error.issues
    .map((i) => `  - ${i.path.join(".")}: ${i.message}`)
    .join("\n");
  throw new Error(
    `[env] ${prefix} inválido(s). Configure no .env / Vercel:\n${lines}`,
  );
}

const clientParsed = clientSchema.safeParse(clientValues);
if (!clientParsed.success) fail("variáveis NEXT_PUBLIC_*", clientParsed.error);

let serverEnv = { CLERK_SECRET_KEY: "" };
if (typeof window === "undefined") {
  const serverSchema = z.object({ CLERK_SECRET_KEY: z.string().min(1) });
  const serverParsed = serverSchema.safeParse({
    CLERK_SECRET_KEY: process.env.CLERK_SECRET_KEY,
  });
  if (!serverParsed.success) fail("variáveis de servidor", serverParsed.error);
  serverEnv = serverParsed.data;
}

export const env = { ...clientParsed.data, ...serverEnv };
