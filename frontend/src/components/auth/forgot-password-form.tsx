"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { LoaderCircle, Mail, LockKeyhole } from "lucide-react";

type ApiMessage = { message?: string; detail?: string };

export function ForgotPasswordForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [step, setStep] = useState<"request" | "reset" | "done">("request");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function requestCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch("/api/auth/request-password-reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
      });
      const data = (await response.json()) as ApiMessage;
      if (!response.ok) {
        setError(data.detail ?? "Unable to send a reset code.");
        return;
      }
      setStep("reset");
      setMessage(data.message ?? "Check your inbox if this account is eligible.");
    } catch {
      setError("Unable to connect to Aqlyra.");
    } finally {
      setLoading(false);
    }
  }

  async function resetPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      const response = await fetch("/api/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          code,
          new_password: password,
        }),
      });
      const data = (await response.json()) as ApiMessage;
      if (!response.ok) {
        setError(data.detail ?? "Unable to reset password.");
        return;
      }
      // Only after a successful single-use recovery code: sign in through
      // the existing secure login endpoint, which sets an HttpOnly cookie.
      let signedIn = false;
      try {
        const login = await fetch("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: email.trim().toLowerCase(),
            password,
          }),
        });
        signedIn = login.ok;
      } catch {
        // The recovery code was already consumed and password updated.
        // Fallback to manual sign-in; never ask to reuse a single-use code.
      }
      setPassword("");
      setConfirmPassword("");
      setCode("");
      if (signedIn) {
        router.replace("/");
        router.refresh();
        return;
      }
      // A login outage or rate limit must never imply the reset failed.
      setMessage("Password updated. Sign in with your new password.");
      setStep("done");
    } catch {
      setError("Unable to connect to Aqlyra.");
    } finally {
      setLoading(false);
    }
  }

  const inputStyle = "mt-2 h-12 w-full rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] px-4 text-sm text-[var(--aq-text)] outline-none focus:border-[var(--aq-blue)]";
  const labelStyle = "mt-5 block text-xs font-semibold text-[var(--aq-text)]";

  return (
    <div className="mt-8">
      {step === "request" && (
        <form onSubmit={requestCode}>
          <label htmlFor="recovery-email" className={labelStyle}>Account email</label>
          <div className="relative">
            <Mail aria-hidden="true" size={17} className="absolute left-4 top-[26px] text-[var(--aq-muted)]" />
            <input id="recovery-email" type="email" autoComplete="email" required
              className={inputStyle + " pl-11"}
              value={email} onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com" />
          </div>
          <button type="submit" disabled={loading}
            className="mt-6 flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-[var(--aq-blue)] text-sm font-semibold text-white disabled:opacity-60">
            {loading && <LoaderCircle size={17} className="animate-spin" />}
            {loading ? "Sending..." : "Send reset code"}
          </button>
          <p className="mt-4 text-center text-xs leading-5 text-[var(--aq-muted)]">
            Registered but your email is not verified yet?{" "}
            <Link href="/verify-email" className="font-semibold text-[var(--aq-blue)] hover:underline">
              Request a verification code instead
            </Link>
          </p>
        </form>
      )}

      {step === "reset" && (
        <form onSubmit={resetPassword}>
          <p className="text-xs leading-6 text-[var(--aq-muted)]">
            If your email is eligible, a six-digit code was sent to {email}.
            It expires in 10 minutes.
          </p>
          <label className={labelStyle} htmlFor="reset-code">6-digit reset code</label>
          <input id="reset-code" type="text" inputMode="numeric" autoComplete="one-time-code"
            required minLength={6} maxLength={6} pattern="[0-9]{6}"
            className={inputStyle + " text-center font-mono tracking-[0.3em]"}
            value={code}
            onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
            placeholder="000000" />
          <label className={labelStyle} htmlFor="new-password">New password</label>
          <div className="relative">
            <LockKeyhole aria-hidden="true" size={17} className="absolute left-4 top-[26px] text-[var(--aq-muted)]" />
            <input id="new-password" type="password" autoComplete="new-password"
              required minLength={8} maxLength={72} className={inputStyle + " pl-11"}
              value={password} onChange={(event) => setPassword(event.target.value)} />
          </div>
          <label className={labelStyle} htmlFor="confirm-password">Confirm password</label>
          <input id="confirm-password" type="password" autoComplete="new-password"
            required minLength={8} maxLength={72} className={inputStyle}
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)} />
          <button type="submit" disabled={loading || code.length !== 6}
            className="mt-6 flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-[var(--aq-blue)] text-sm font-semibold text-white disabled:opacity-60">
            {loading && <LoaderCircle size={17} className="animate-spin" />}
            {loading ? "Updating..." : "Set new password"}
          </button>
          <button type="button" className="mt-4 w-full text-xs font-semibold text-[var(--aq-blue)]"
            onClick={() => { setStep("request"); setCode(""); setError(""); setMessage(""); }}>
            Request another code
          </button>
        </form>
      )}

      {step === "done" && (
        <Link href="/login"
          className="mt-5 flex h-12 items-center justify-center rounded-xl bg-[var(--aq-blue)] text-sm font-semibold text-white">
          Sign in with your new password
        </Link>
      )}
      {error && <p role="alert" className="mt-5 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-xs text-red-400">{error}</p>}
      {message && <p role="status" className="mt-5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-xs text-emerald-300">{message}</p>}
    </div>
  );
}
