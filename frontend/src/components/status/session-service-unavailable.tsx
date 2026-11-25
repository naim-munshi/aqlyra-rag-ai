"use client";

import { useEffect, useState } from "react";

/**
 * Server Components cannot write HttpOnly cookies. This screen asks the
 * writable /api/auth/me Route Handler to renew the access token, preserving
 * the existing refresh cookie during transient Render cold starts.
 */
export function SessionServiceUnavailable() {
  const [message, setMessage] = useState("Checking your saved session…");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;
    let count = 0;

    const recover = async () => {
      if (cancelled) return;
      count += 1;
      setAttempt(count);
      controller = new AbortController();
      const deadline = setTimeout(() => controller?.abort(), 12_000);

      try {
        const response = await fetch("/api/auth/me", {
          cache: "no-store",
          signal: controller.signal,
        });
        if (cancelled) return;
        if (response.ok) {
          window.location.reload();
          return;
        }
        if (response.status === 401 || response.status === 403) {
          setMessage("Your session has expired. Please sign in again.");
          return;
        }
        setMessage("The service is waking up. Your session has been kept.");
      } catch {
        if (!cancelled) {
          setMessage("The service is temporarily unavailable. Your session has been kept.");
        }
      } finally {
        clearTimeout(deadline);
      }

      if (!cancelled && count < 5) {
        timer = setTimeout(() => void recover(), 5_000);
      }
    };

    void recover();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      controller?.abort();
    };
  }, []);

  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--aq-bg)] px-5 py-12 text-[var(--aq-text)]">
      <section role="status" className="w-full max-w-md rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-7">
        <h1 className="text-xl font-semibold">Aqlyra is reconnecting</h1>
        <p className="mt-4 text-sm leading-7 text-[var(--aq-muted)]">{message}</p>
        <p className="mt-3 text-sm text-[var(--aq-muted)]">Recovery attempt {attempt}/5</p>
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
