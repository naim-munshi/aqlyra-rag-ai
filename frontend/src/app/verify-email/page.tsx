import Link from "next/link";

import { VerifyEmailForm } from "@/components/auth/verify-email-form";
import { AqlyraLogo } from "@/components/brand/aqlyra-logo";

export default function VerifyEmailPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--aq-bg)] px-6 py-12 text-[var(--aq-text)]">
      <div className="w-full max-w-[440px]">
        <div className="mb-8 flex justify-center">
          <AqlyraLogo size={46} />
        </div>

        <div className="rounded-3xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-8 shadow-2xl sm:p-10">
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[var(--aq-cyan)]">
            Verify your email
          </p>
          <h1 className="mt-3 text-[32px] font-bold tracking-tight">
            Check your inbox
          </h1>
          <p className="mt-3 text-[15px] leading-6 text-[var(--aq-muted)]">
            Enter the one-time code sent by Aqlyra. The code
            expires in 10 minutes.
          </p>

          <VerifyEmailForm />

          <div className="mt-7 border-t border-[var(--aq-border)] pt-6 text-center text-sm text-[var(--aq-muted)]">
            Already verified?{" "}
            <Link
              href="/login"
              className="font-semibold text-[var(--aq-blue)] hover:underline"
            >
              Sign in
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
