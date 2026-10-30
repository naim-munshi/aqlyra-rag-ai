"use client";

import { useCallback, useRef, useState } from "react";
import { LoaderCircle } from "lucide-react";
import Script from "next/script";
import { useRouter } from "next/navigation";

type GoogleCredentialResponse = {
  credential?: string;
};

type GoogleAccounts = {
  id: {
    initialize: (options: {
      client_id: string;
      callback: (response: GoogleCredentialResponse) => void;
    }) => void;
    renderButton: (
      element: HTMLElement,
      options: {
        type: "standard";
        theme: "filled_black";
        size: "large";
        text: "continue_with";
        shape: "rectangular";
        width: number;
      },
    ) => void;
  };
};

declare global {
  interface Window {
    google?: {
      accounts: GoogleAccounts;
    };
  }
}

type ApiError = {
  detail?: string;
};

export function GoogleSignInButton() {
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const clientId =
    process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID?.trim() ?? "";

  const authenticate = useCallback(
    async (response: GoogleCredentialResponse) => {
      if (!response.credential) {
        setError("Google did not return a sign-in credential.");
        return;
      }

      setLoading(true);
      setError("");

      try {
        const loginResponse = await fetch("/api/auth/google", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            credential: response.credential,
          }),
        });
        const data = (await loginResponse.json()) as ApiError;

        if (!loginResponse.ok) {
          setError(
            typeof data.detail === "string"
              ? data.detail
              : "Google sign-in failed.",
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
    },
    [router],
  );

  const initializeGoogle = useCallback(() => {
    if (
      !clientId ||
      !window.google ||
      !containerRef.current
    ) {
      return;
    }

    window.google.accounts.id.initialize({
      client_id: clientId,
      callback: (response) => {
        void authenticate(response);
      },
    });

    containerRef.current.replaceChildren();
    window.google.accounts.id.renderButton(
      containerRef.current,
      {
        type: "standard",
        theme: "filled_black",
        size: "large",
        text: "continue_with",
        shape: "rectangular",
        width: Math.max(
          200,
          Math.min(400, containerRef.current.clientWidth),
        ),
      },
    );
  }, [authenticate, clientId]);

  if (!clientId) {
    return (
      <div className="mt-7" data-google-oauth-status="not-configured">
        <button
          type="button"
          disabled
          aria-disabled="true"
          className="flex min-h-12 w-full cursor-not-allowed items-center justify-center gap-3 rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] px-4 text-sm font-semibold text-[var(--aq-muted)] opacity-80"
        >
          <span aria-hidden="true" className="text-lg font-bold">G</span>
          Continue with Google
          <span className="ml-auto text-[10px] font-medium">Unavailable</span>
        </button>
        <p className="mt-2 text-center text-xs leading-5 text-[var(--aq-muted)]" role="status">
          Google sign-in is not configured yet. Use email and password for now.
        </p>
      </div>
    );
  }

  return (
    <div className="mt-8">
      <Script
        src="https://accounts.google.com/gsi/client"
        strategy="afterInteractive"
        onReady={initializeGoogle}
        onError={() => setError("Google sign-in could not load. Open this page in Safari or Chrome and retry.")}
      />

      {loading && (
        <div className="flex h-11 items-center justify-center gap-2 rounded-lg border border-[var(--aq-border)] text-sm text-[var(--aq-muted)]">
          <LoaderCircle size={17} className="animate-spin" />
          Signing in with Google...
        </div>
      )}

      <div
        ref={containerRef}
        className={
          loading
            ? "hidden"
            : "flex min-h-11 justify-center"
        }
      />

      {error && (
        <div className="mt-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-xs text-red-400">
          {error}
        </div>
      )}

      <div className="mt-6 flex items-center gap-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--aq-muted)]">
        <span className="h-px flex-1 bg-[var(--aq-border)]" />
        or use email
        <span className="h-px flex-1 bg-[var(--aq-border)]" />
      </div>
    </div>
  );
}
