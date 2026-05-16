"use client";

import { useAuth } from "@clerk/nextjs";
import { useMemo } from "react";

import { ApiClient } from "./api";

export function useApiClient(): ApiClient {
  const { getToken } = useAuth();
  return useMemo(
    () =>
      new ApiClient(
        process.env.NEXT_PUBLIC_API_URL as string,
        () => getToken(),
      ),
    [getToken],
  );
}
