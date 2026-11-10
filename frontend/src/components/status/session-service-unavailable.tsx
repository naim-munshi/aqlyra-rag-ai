"use client";

/**
 * Show a recoverable outage without treating a transient authentication
 * provider failure as logout or exposing the private workspace.
 */
export function SessionServiceUnavailable() {
  return (
    <main
      className="flex min-h-screen items-center justify-center bg-[var(--aq-bg)] px-5 py-12 text-[var(--aq-text)]"
      role="main"
    >
      <section
        role="alert"
        className="w-full max-w-md rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-7"
      >
        <h1 className="text-xl font-semibold">Aqlyra is temporarily unavailable</h1>
        <p className="mt-4 text-sm leading-7 text-[var(--aq-muted)]">
          We could not reach the session service. Your saved documents and
          account have not been cleared. Please retry once the connection
          recovers.
        </p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="mt-6 rounded-xl bg-[var(--aq-blue)] px-5 py-3 text-sm font-semibold text-white"
        >
          Retry connection
        </button>
      </section>
    </main>
  );
}
