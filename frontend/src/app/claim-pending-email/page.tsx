"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

type ApiMessage = { detail?: string; message?: string; success?: boolean };

export default function ClaimPendingEmailPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [code, setCode] = useState("");
  const [requested, setRequested] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function requestCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch("/api/auth/resend-verification", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
      });
      const data = (await response.json()) as ApiMessage;
      if (!response.ok) {
        throw new Error(data.detail ?? "Please try again after the cooldown.");
      }
      setRequested(true);
      setNotice("If this email has a pending account, a verification code will be sent to its mailbox.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Service unavailable");
    } finally {
      setLoading(false);
    }
  }

  async function claim(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/auth/claim-pending-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: username.trim().toLowerCase(),
          code,
          new_password: newPassword,
        }),
      });
      const data = (await response.json()) as ApiMessage;
      if (!response.ok || data.success !== true) {
        throw new Error(data.detail ?? "Unable to claim pending account.");
      }
      router.push("/");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Service unavailable");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-[var(--aq-bg)] px-5 py-12 text-[var(--aq-text)]">
      <div className="mx-auto max-w-md rounded-3xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-7 sm:p-9">
        <Link href="/login" className="text-sm text-[var(--aq-blue)] hover:underline">
          Back to sign in
        </Link>
        <h1 className="mt-5 text-2xl font-bold">Claim a pending email account</h1>
        <p className="mt-3 text-sm leading-6 text-[var(--aq-muted)]">
          If someone created an unverified registration with your email,
          request a code to your mailbox. Only the holder of that mailbox can
          replace pending account credentials. Verified accounts use password reset instead.
        </p>
        <form onSubmit={requestCode} className="mt-7 space-y-3">
          <label htmlFor="claim-email" className="block text-sm font-semibold">Your email</label>
          <input
            id="claim-email" type="email" required autoComplete="email" value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="h-12 w-full rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] px-4 text-sm"
          />
          <button type="submit" disabled={loading || !email.trim()}
            className="h-12 w-full rounded-xl bg-[var(--aq-blue)] text-sm font-semibold text-white disabled:opacity-60">
            {loading ? "Sending..." : "Request mailbox verification code"}
          </button>
        </form>
        {requested && (
          <form onSubmit={claim} className="mt-7 space-y-4 border-t border-[var(--aq-border)] pt-6">
            <p className="text-xs text-[var(--aq-muted)]">
              Code expires after 10 minutes. Set your own username and password
              after confirming mailbox ownership.
            </p>
            <label htmlFor="claim-code" className="block text-sm font-semibold">6-digit code</label>
            <input id="claim-code" required inputMode="numeric" autoComplete="one-time-code"
              pattern="[0-9]{6}" minLength={6} maxLength={6} value={code}
              onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
              className="h-12 w-full rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] px-4 text-sm" />
            <label htmlFor="claim-username" className="block text-sm font-semibold">New username</label>
            <input id="claim-username" required minLength={3} maxLength={50}
              pattern="[a-zA-Z0-9_-]+" autoComplete="username" value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="h-12 w-full rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] px-4 text-sm" />
            <label htmlFor="claim-password" className="block text-sm font-semibold">New password</label>
            <input id="claim-password" type="password" required minLength={8} maxLength={72}
              autoComplete="new-password" value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              className="h-12 w-full rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] px-4 text-sm" />
            <button type="submit" disabled={loading || code.length !== 6}
              className="h-12 w-full rounded-xl bg-[var(--aq-blue)] text-sm font-semibold text-white disabled:opacity-60">
              {loading ? "Verifying..." : "Verify and secure my account"}
            </button>
          </form>
        )}
        {notice && <p role="status" className="mt-4 text-sm text-[var(--aq-muted)]">{notice}</p>}
        {error && <p role="alert" className="mt-4 text-sm text-red-400">{error}</p>}
      </div>
    </main>
  );
}
