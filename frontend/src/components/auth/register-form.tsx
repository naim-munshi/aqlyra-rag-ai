"use client";

import { FormEvent, useState } from "react";
import {
  Eye,
  EyeOff,
  LoaderCircle,
  LockKeyhole,
  Mail,
  User,
} from "lucide-react";
import { useRouter } from "next/navigation";

type ApiError = {
  detail?:
    | string
    | Array<{
        msg?: string;
      }>;
};

function getErrorMessage(data: ApiError) {
  if (typeof data.detail === "string") {
    return data.detail;
  }

  if (Array.isArray(data.detail)) {
    return data.detail[0]?.msg ?? "Invalid account information.";
  }

  return "Unable to create account.";
}

export function RegisterForm() {
  const router = useRouter();

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] =
    useState("");

  const [showPassword, setShowPassword] =
    useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    setError("");

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);

    try {
      const registerResponse = await fetch(
        "/api/auth/register",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            username,
            email,
            password,
          }),
        },
      );

      const registerData =
        (await registerResponse.json()) as ApiError;

      if (!registerResponse.ok) {
        setError(getErrorMessage(registerData));
        return;
      }

      const loginResponse = await fetch(
        "/api/auth/login",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            email,
            password,
          }),
        },
      );

      const loginData =
        (await loginResponse.json()) as ApiError;

      if (!loginResponse.ok) {
        setError(getErrorMessage(loginData));
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
    <form
      onSubmit={handleSubmit}
      className="mt-8"
    >
      <div>
        <label
          htmlFor="username"
          className="text-xs font-semibold text-[var(--aq-text)]"
        >
          Username
        </label>

        <div className="mt-2 flex h-12 items-center gap-3 rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] px-4 focus-within:border-[var(--aq-blue)]">
          <User
            size={17}
            className="text-[var(--aq-muted)]"
          />

          <input
            id="username"
            value={username}
            onChange={(event) =>
              setUsername(event.target.value)
            }
            minLength={3}
            maxLength={50}
            pattern="[A-Za-z0-9_-]+"
            autoComplete="username"
            required
            placeholder="your_username"
            className="min-w-0 flex-1 bg-transparent text-sm text-[var(--aq-text)] outline-none placeholder:text-[var(--aq-muted)]"
          />
        </div>

        <p className="mt-2 text-[10px] text-[var(--aq-muted)]">
          Letters, numbers, underscore and hyphen only.
        </p>
      </div>

      <div className="mt-5">
        <label
          htmlFor="register-email"
          className="text-xs font-semibold text-[var(--aq-text)]"
        >
          Email
        </label>

        <div className="mt-2 flex h-12 items-center gap-3 rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] px-4 focus-within:border-[var(--aq-blue)]">
          <Mail
            size={17}
            className="text-[var(--aq-muted)]"
          />

          <input
            id="register-email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) =>
              setEmail(event.target.value)
            }
            placeholder="you@example.com"
            className="min-w-0 flex-1 bg-transparent text-sm text-[var(--aq-text)] outline-none placeholder:text-[var(--aq-muted)]"
          />
        </div>
      </div>

      <div className="mt-5">
        <label
          htmlFor="register-password"
          className="text-xs font-semibold text-[var(--aq-text)]"
        >
          Password
        </label>

        <div className="mt-2 flex h-12 items-center gap-3 rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] px-4 focus-within:border-[var(--aq-blue)]">
          <LockKeyhole
            size={17}
            className="text-[var(--aq-muted)]"
          />

          <input
            id="register-password"
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            required
            minLength={8}
            maxLength={72}
            value={password}
            onChange={(event) =>
              setPassword(event.target.value)
            }
            placeholder="Minimum 8 characters"
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
            className="text-[var(--aq-muted)]"
          >
            {showPassword ? (
              <EyeOff size={17} />
            ) : (
              <Eye size={17} />
            )}
          </button>
        </div>
      </div>

      <div className="mt-5">
        <label
          htmlFor="confirm-password"
          className="text-xs font-semibold text-[var(--aq-text)]"
        >
          Confirm password
        </label>

        <div className="mt-2 flex h-12 items-center gap-3 rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] px-4 focus-within:border-[var(--aq-blue)]">
          <LockKeyhole
            size={17}
            className="text-[var(--aq-muted)]"
          />

          <input
            id="confirm-password"
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            required
            minLength={8}
            maxLength={72}
            value={confirmPassword}
            onChange={(event) =>
              setConfirmPassword(event.target.value)
            }
            placeholder="Repeat your password"
            className="min-w-0 flex-1 bg-transparent text-sm text-[var(--aq-text)] outline-none placeholder:text-[var(--aq-muted)]"
          />
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

        {loading
          ? "Creating account..."
          : "Create account"}
      </button>
    </form>
  );
}