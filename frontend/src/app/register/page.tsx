import Link from "next/link";
import {
  FileSearch,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

import { RegisterForm } from "@/components/auth/register-form";
import { AqlyraLogo } from "@/components/brand/aqlyra-logo";

export default function RegisterPage() {
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
              Build your
              <span className="block text-[var(--aq-blue)]">
                knowledge workspace.
              </span>
            </h1>

            <p className="mt-4 max-w-[285px] text-xs leading-6 text-[var(--aq-muted)]">
              Upload private documents and generate grounded answers
              with source citations.
            </p>

            <div className="mt-8 space-y-3">
              <Feature
                icon={FileSearch}
                title="Document retrieval"
              />

              <Feature
                icon={ShieldCheck}
                title="Traceable citations"
              />
            </div>
          </div>

          <p className="text-[10px] text-[var(--aq-muted)]">
            Aqlyra RAG AI
          </p>
        </aside>

        {/* Register */}
        <section className="flex min-h-screen items-center justify-center px-6 py-10">
          <div className="w-full max-w-[440px] lg:scale-105 xl:scale-110">
            <div className="mb-8 lg:hidden">
              <AqlyraLogo size={46} />
            </div>

            <div className="rounded-3xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-8 shadow-2xl sm:p-10">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[var(--aq-cyan)]">
                Get started
              </p>

              <h2 className="mt-3 text-[32px] font-bold tracking-tight">
                Create your account
              </h2>

              <p className="mt-3 text-[15px] leading-6 text-[var(--aq-muted)]">
                Set up your private Aqlyra workspace.
              </p>

              <RegisterForm />

              <div className="mt-7 border-t border-[var(--aq-border)] pt-6 text-center text-sm text-[var(--aq-muted)]">
                Already have an account?{" "}
                <Link
                  href="/login"
                  className="font-semibold text-[var(--aq-blue)] hover:underline"
                >
                  Sign in
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