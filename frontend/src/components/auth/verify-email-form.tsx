"use client";

import { FormEvent, useEffect, useState } from "react";
import { LoaderCircle, MailCheck } from "lucide-react";
import { useRouter } from "next/navigation";

type ApiResponse = {
  detail?: string;
  message?: string;
};

export function VerifyEmailForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const pendingEmail = window.sessionStorage.getItem(
        "aqlyra_pending_email",
      );

      if (pendingEmail) {
        setEmail(pendingEmail);
      }
    }, 0);

    return () => window.clearTimeout(timer);
  }, []);

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    setError("");
    setMessage("");
    setLoading(true);

    try {
      const response = await fetch("/api/auth/verify-email", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          code,
        }),
      });
      const data = (await response.json()) as ApiResponse;

      if (!response.ok) {
        setError(
          typeof data.detail === "string"
            ? data.detail
            : "Unable to verify this code.",
        );
        return;
      }

      window.sessionStorage.removeItem("aqlyra_pending_email");
      router.push("/");
      router.refresh();
    } catch {
      setError("Unable to connect to Aqlyra.");
    } finally {
      setLoading(false);
    }
  }

  async function handleResend() {
    if (!email.trim()) {
      setError("Enter your email address first.");
      return;
    }

    setError("");
    setMessage("");
    setResending(true);

    try {
      const response = await fetch(
        "/api/auth/resend-verification",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            email: email.trim().toLowerCase(),
          }),
        },
      );
      const data = (await response.json()) as ApiResponse;

      if (!response.ok) {
        setError(
          typeof data.detail === "string"
            ? data.detail
            : "Unable to resend the code.",
        );
        return;
      }

      setMessage(
        data.message ?? "A new verification code was sent.",
      );
    } catch {
      setError("Unable to connect to Aqlyra.");
    } finally {
      setResending(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-8">
      <label
        htmlFor="verify-email"
        className="text-xs font-semibold text-[var(--aq-text)]"
      >
        Email
      </label>

      <div className="mt-2 flex h-12 items-center gap-3 rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] px-4 focus-within:border-[var(--aq-blue)]">
        <MailCheck size={17} className="text-[var(--aq-muted)]" />
        <input
          id="verify-email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="you@example.com"
          className="min-w-0 flex-1 bg-transparent text-sm text-[var(--aq-text)] outline-none placeholder:text-[var(--aq-muted)]"
        />
      </div>

      <label
        htmlFor="verification-code"
        className="mt-5 block text-xs font-semibold text-[var(--aq-text)]"
      >
        6-digit code
      </label>

      <input
        id="verification-code"
        type="text"
        inputMode="numeric"
        autoComplete="one-time-code"
        required
        minLength={6}
        maxLength={6}
        pattern="[0-9]{6}"
        value={code}
        onChange={(event) =>
          setCode(
            event.target.value.replace(/\D/g, "").slice(0, 6),
          )
        }
        placeholder="000000"
        className="mt-2 h-14 w-full rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] px-4 text-center font-mono text-2xl tracking-[0.35em] text-[var(--aq-text)] outline-none focus:border-[var(--aq-blue)]"
      />

      {error && (
        <div className="mt-5 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-xs text-red-400">
          {error}
        </div>
      )}

      {message && (
        <div className="mt-5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-xs text-emerald-300">
          {message}
        </div>
      )}

      <button
        type="submit"
        disabled={loading || code.length !== 6}
        className="mt-6 flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-[var(--aq-blue)] text-sm font-semibold text-white transition hover:bg-[var(--aq-blue-hover)] disabled:opacity-60"
      >
        {loading && (
          <LoaderCircle size={17} className="animate-spin" />
        )}
        {loading ? "Verifying..." : "Verify and continue"}
      </button>

      <button
        type="button"
        disabled={resending}
        onClick={() => void handleResend()}
        className="mt-4 w-full text-xs font-semibold text-[var(--aq-blue)] disabled:opacity-60"
      >
        {resending ? "Sending..." : "Did not receive it? Resend code"}
      </button>
    </form>
  );
}
