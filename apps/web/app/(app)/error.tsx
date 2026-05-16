"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <div className="mx-auto max-w-xl p-8">
      <Alert variant="destructive">
        <AlertTitle>Algo deu errado</AlertTitle>
        <AlertDescription>
          Um erro inesperado aconteceu nesta tela. A equipe foi notificada
          automaticamente.
        </AlertDescription>
      </Alert>
      <Button className="mt-4" onClick={() => reset()}>
        Tentar novamente
      </Button>
    </div>
  );
}
