"use client";

import { FormEvent, useState } from "react";
import {
  Eye,
  EyeOff,
  LoaderCircle,
  LockKeyhole,
  Mail,
} from "lucide-react";
import { useRouter } from "next/navigation";

type LoginError = {
  detail?: string;
};

export function LoginForm() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    setError("");
    setLoading(true);

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email,
          password,
        }),
      });

      const data = (await response.json()) as LoginError;

      if (!response.ok) {
        setError(
          typeof data.detail === "string"
            ? data.detail
            : "Unable to sign in.",
        );

        return;
      }

      router.push("/");
      router.refresh();
    } catch {
      setError("Unable to connect to Aqlyra.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-8">
      <div>
        <label
          htmlFor="email"
          className="text-xs font-semibold text-[var(--aq-text)]"
        >
          Email
        </label>

        <div className="mt-2 flex h-12 items-center gap-3 rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] px-4 focus-within:border-[var(--aq-blue)]">
          <Mail
            size={17}
            className="shrink-0 text-[var(--aq-muted)]"
          />

          <input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
            className="min-w-0 flex-1 bg-transparent text-sm text-[var(--aq-text)] outline-none placeholder:text-[var(--aq-muted)]"
          />
        </div>
      </div>

      <div className="mt-5">
        <div className="flex items-center justify-between">
          <label
            htmlFor="password"
            className="text-xs font-semibold text-[var(--aq-text)]"
          >
            Password
          </label>

          <button
            type="button"
            className="text-xs font-semibold text-[var(--aq-blue)]"
          >
            Forgot password?
          </button>
        </div>

        <div className="mt-2 flex h-12 items-center gap-3 rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] px-4 focus-within:border-[var(--aq-blue)]">
          <LockKeyhole
            size={17}
            className="shrink-0 text-[var(--aq-muted)]"
          />

          <input
            id="password"
            type={showPassword ? "text" : "password"}
            autoComplete="current-password"
            required
            minLength={8}
            maxLength={72}
            value={password}
            onChange={(event) =>
              setPassword(event.target.value)
            }
            placeholder="Enter your password"
            className="min-w-0 flex-1 bg-transparent text-sm text-[var(--aq-text)] outline-none placeholder:text-[var(--aq-muted)]"
          />

          <button
            type="button"
            aria-label={
              showPassword
                ? "Hide password"
                : "Show password"
            }
            onClick={() =>
              setShowPassword((value) => !value)
            }
            className="text-[var(--aq-muted)] transition hover:text-[var(--aq-text)]"
          >
            {showPassword ? (
              <EyeOff size={17} />
            ) : (
              <Eye size={17} />
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="mt-5 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-xs text-red-400">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={loading}
        className="mt-6 flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-[var(--aq-blue)] text-sm font-semibold text-white transition hover:bg-[var(--aq-blue-hover)] disabled:opacity-60"
      >
        {loading && (
          <LoaderCircle
            size={17}
            className="animate-spin"
          />
        )}

        {loading ? "Signing in..." : "Sign in"}
      </button>
    </form>
  );
}