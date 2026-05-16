"use client";

import * as Sentry from "@sentry/nextjs";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";

/** Dev-only: dispara um erro de teste pro Sentry web (#88 DoD 1). */
export function SentryTestButton() {
  return (
    <Button
      variant="outline"
      onClick={() => {
        const err = new Error("UpHiring Sentry test error (dev button)");
        Sentry.captureException(err);
        toast.success("Erro de teste enviado ao Sentry.");
      }}
    >
      Disparar erro de teste (Sentry)
    </Button>
  );
}
