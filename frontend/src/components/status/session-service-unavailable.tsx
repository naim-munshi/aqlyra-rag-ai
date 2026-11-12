"use client";

import { useEffect, useState } from "react";

import {
  canReloadAfterRecovery,
  RECOVERY_CHECK_INTERVAL_MS,
  RECOVERY_CHECK_TIMEOUT_MS,
  RECOVERY_MAX_CHECKS,
} from "@/lib/status/recovery";

/**
 * A Render Free cold start can take longer than a single Vercel request.
 * Probe one request at a time, without credentials or document contents,
 * then confirm the existing session endpoint before refreshing the page.
 * Never clear cookies, mutate user data, or enter a reload loop on 5xx.
 */
export function SessionServiceUnavailable() {
  const [checks, setChecks] = useState(0);
  const [reconnecting, setReconnecting] = useState(true);

  useEffect(() => {
    let disposed = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let activeController: AbortController | null = null;
    let attempted = 0;

    async function checkConnection(): Promise<void> {
      if (disposed) return;
      attempted += 1;
      setChecks(attempted);

      const controller = new AbortController();
      activeController = controller;
      const deadline = setTimeout(
        () => controller.abort(),
        RECOVERY_CHECK_TIMEOUT_MS,
      );

      try {
        // A GET to the health endpoint also starts an idle Render instance.
        const health = await fetch("/api/health", {
          cache: "no-store",
          signal: controller.signal,
        });
        if (health.status === 200) {
          const body: unknown = await health.json();
          if (
            typeof body === "object" &&
            body !== null &&
            "status" in body &&
            body.status === "ready"
          ) {
            // 5xx/transport errors must retain the user's HttpOnly cookies.
            // Do not refresh indefinitely while the auth path is unavailable.
            const session = await fetch("/api/auth/me", {
              cache: "no-store",
              signal: controller.signal,
            });
            if (
              !disposed &&
              canReloadAfterRecovery(health.status, body, session.status)
            ) {
              window.location.reload();
              return;
            }
          }
        }
      } catch {
        // Connection errors are expected while Render is waking up.
      } finally {
        clearTimeout(deadline);
        if (activeController === controller) activeController = null;
      }

      if (disposed) return;
      if (attempted >= RECOVERY_MAX_CHECKS) {
        setReconnecting(false);
      } else {
        timer = setTimeout(
          () => void checkConnection(),
          RECOVERY_CHECK_INTERVAL_MS,
        );
      }
    }

    void checkConnection();
    return () => {
      disposed = true;
      if (timer) clearTimeout(timer);
      activeController?.abort();
    };
  }, []);

  return (
    <main
      className="flex min-h-screen items-center justify-center bg-[var(--aq-bg)] px-5 py-12 text-[var(--aq-text)]"
      role="main"
    >
      <section
        role="alert"
        className="w-full max-w-md rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-7"
      >
        <h1 className="text-xl font-semibold">
          Aqlyra is reconnecting
        </h1>
        <p className="mt-4 text-sm leading-7 text-[var(--aq-muted)]">
          The AI service may be waking up after a period of inactivity.
          Your saved documents and account have not been cleared.
        </p>
        <p className="mt-3 text-sm text-[var(--aq-muted)]" aria-live="polite">
          {reconnecting
            ? `Checking the connection automatically (${checks}/${RECOVERY_MAX_CHECKS})…`
            : "Still unavailable. Please try again shortly."}
        </p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="mt-6 rounded-xl bg-[var(--aq-blue)] px-5 py-3 text-sm font-semibold text-white"
        >
          Retry now
        </button>
      </section>
    </main>
  );
}
