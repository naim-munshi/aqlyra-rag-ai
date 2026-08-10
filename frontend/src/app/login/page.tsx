import Link from "next/link";
import {
  FileSearch,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

import { LoginForm } from "@/components/auth/login-form";
import { AqlyraLogo } from "@/components/brand/aqlyra-logo";

export default function LoginPage() {
  return (
    <main className="min-h-screen bg-[var(--aq-bg)] text-[var(--aq-text)]">
      <div className="grid min-h-screen lg:grid-cols-[380px_1fr]">
        {/* Left side */}
        <aside className="hidden border-r border-[var(--aq-border)] bg-[var(--aq-bg-deep)] px-10 py-10 lg:flex lg:flex-col">
          <AqlyraLogo size={46} />

          <div className="my-auto">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[var(--aq-cyan)]">
              Private Knowledge AI
            </p>

            <h1 className="mt-4 max-w-[290px] text-3xl font-bold leading-tight tracking-tight">
              Ask your documents.
              <span className="block text-[var(--aq-blue)]">
                Get grounded answers.
              </span>
            </h1>

            <p className="mt-4 max-w-[285px] text-xs leading-6 text-[var(--aq-muted)]">
              Search private knowledge and generate answers with
              traceable citations.
            </p>

            <div className="mt-8 space-y-3">
              <Feature
                icon={FileSearch}
                title="Knowledge retrieval"
              />

              <Feature
                icon={ShieldCheck}
                title="Grounded citations"
              />
            </div>
          </div>

          <p className="text-[10px] text-[var(--aq-muted)]">
            Aqlyra RAG AI
          </p>
        </aside>

        {/* Login */}
        <section className="flex min-h-screen items-center justify-center px-6 py-12">
          <div className="w-full max-w-[440px] lg:scale-105 xl:scale-110">
            <div className="mb-10 lg:hidden">
              <AqlyraLogo size={46} />
            </div>

            <div className="rounded-3xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-8 shadow-2xl sm:p-10">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[var(--aq-cyan)]">
                Welcome back
              </p>

              <h2 className="mt-3 text-[32px] font-bold tracking-tight">
                Sign in to Aqlyra
              </h2>

              <p className="mt-3 text-[15px] leading-6 text-[var(--aq-muted)]">
                Continue to your knowledge workspace.
              </p>

              <LoginForm />

              <div className="mt-7 border-t border-[var(--aq-border)] pt-6 text-center text-sm text-[var(--aq-muted)]">
                New to Aqlyra?{" "}
                <Link
                  href="/register"
                  className="font-semibold text-[var(--aq-blue)] hover:underline"
                >
                  Create account
                </Link>
              </div>
            </div>

            <p className="mt-5 text-center text-xs text-[var(--aq-muted)]">
              Private • Grounded • Citation-aware
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}

type FeatureProps = {
  icon: LucideIcon;
  title: string;
};

function Feature({
  icon: Icon,
  title,
}: FeatureProps) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--aq-border)] bg-[var(--aq-blue-soft)] text-[var(--aq-blue)]">
        <Icon size={16} />
      </div>

      <p className="text-xs font-semibold text-[var(--aq-text)]">
        {title}
      </p>
    </div>
  );
}