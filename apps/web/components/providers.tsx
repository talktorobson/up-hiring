"use client";

import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { useState } from "react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api-types";

function handleApiError(error: unknown) {
  if (!(error instanceof ApiError)) {
    toast.error("Algo deu errado. Tente novamente.");
    return;
  }
  if (error.status === 401) {
    if (typeof window !== "undefined") {
      window.location.href = `/sign-in?redirect_url=${encodeURIComponent(
        window.location.pathname,
      )}`;
    }
    return;
  }
  // 422/409 são tratados campo-a-campo nos forms; só notifica os demais.
  if (error.status !== 422 && error.status !== 409) {
    toast.error(`Erro ${error.status}: ${error.code}`);
  }
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
        queryCache: new QueryCache({ onError: handleApiError }),
        mutationCache: new MutationCache({ onError: handleApiError }),
      }),
  );

  return (
    <QueryClientProvider client={client}>
      {children}
      {process.env.NODE_ENV === "development" && (
        <ReactQueryDevtools initialIsOpen={false} />
      )}
    </QueryClientProvider>
  );
}
