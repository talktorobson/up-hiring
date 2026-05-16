"use client";

import { useAuth } from "@clerk/nextjs";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

import { initTelemetry, recordEvent } from "@/lib/telemetry";

/**
 * Monta o OTel web e emite spans de page view + login. Fetch é
 * auto-instrumentado pelo FetchInstrumentation (cobre o ApiClient).
 */
export function Telemetry() {
  const pathname = usePathname();
  const { isSignedIn } = useAuth();
  const wasSignedIn = useRef(false);

  useEffect(() => {
    initTelemetry();
  }, []);

  useEffect(() => {
    recordEvent("page_view", { "page.path": pathname });
  }, [pathname]);

  useEffect(() => {
    if (isSignedIn && !wasSignedIn.current) {
      recordEvent("clerk.login");
    }
    wasSignedIn.current = !!isSignedIn;
  }, [isSignedIn]);

  return null;
}
