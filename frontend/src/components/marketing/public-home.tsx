import Link from "next/link";

import { AqlyraLogo } from "@/components/brand/aqlyra-logo";

const features = [
  {
    label: "01",
    title: "Ask your documents",
    description:
      "Search selected documents and ask questions. Aqlyra can ground answers in retrieved passages with reviewable source references.",
  },
  {
    label: "02",
    title: "Converse with AI",
    description:
      "Use general AI chat for ideas, explanations and everyday questions. Model responses may contain errors and should be checked.",
  },
  {
    label: "03",
    title: "Explore web research",
    description:
      "Research public information with sources, where supported by the configured provider and available tools.",
  },
  {
    label: "04",
    title: "Plan your studies",
    description:
      "Organize Study Abroad research and compare academic requirements. Always confirm admissions and visa criteria with official institutions.",
  },
] as const;

const structuredData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebSite",
      name: "Aqlyra",
      url: "https://aqlyra-ai.vercel.app/",
      description: "Aqlyra AI knowledge workspace with source-grounded document search and AI conversations.",
    },
    {
      "@type": "WebApplication",
      "@id": "https://aqlyra-ai.vercel.app/#software",
      name: "Aqlyra",
      url: "https://aqlyra-ai.vercel.app/",
      applicationCategory: "BusinessApplication",
      operatingSystem: "Web",
      sameAs: "https://github.com/naim-munshi/aqlyra-rag-ai",
      description:
        "AI assistant with document retrieval, citation-aware answers, web research and Study Abroad planning tools.",
    },
  ],
};

export function PublicHomePage() {
  return (
    <main className="min-h-screen overflow-hidden bg-[var(--aq-bg)] text-[var(--aq-text)]">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(structuredData).replace(/</g, "\\u003c"),
        }}
      />
      <div className="mx-auto max-w-6xl px-5 sm:px-8">
        <header className="flex flex-wrap items-center justify-between gap-5 border-b border-[var(--aq-border)] py-6">
          <Link href="/" aria-label="Aqlyra home">
            <AqlyraLogo size={39} />
          </Link>
          <nav aria-label="Main navigation" className="flex flex-wrap items-center gap-4 text-sm sm:gap-6">
            <Link href="/about" className="text-[var(--aq-muted)] transition hover:text-[var(--aq-text)]">About</Link>
            <Link href="/how-it-works" className="text-[var(--aq-muted)] transition hover:text-[var(--aq-text)]">How it works</Link>
            <Link href="/demo" className="text-[var(--aq-muted)] transition hover:text-[var(--aq-text)]">Demo</Link>
            <Link href="/help" className="text-[var(--aq-muted)] transition hover:text-[var(--aq-text)]">Help</Link>
            <Link href="/login" className="rounded-xl border border-[var(--aq-border)] px-4 py-2 font-semibold hover:border-[var(--aq-blue)]">
              Sign in
            </Link>
          </nav>
        </header>

        <section className="relative py-20 sm:py-28" aria-labelledby="aqlyra-home-heading">
          <div aria-hidden="true" className="pointer-events-none absolute -right-48 top-12 h-96 w-96 rounded-full bg-[var(--aq-blue)] opacity-[0.08] blur-3xl" />
          <div className="relative max-w-3xl">
            <p className="inline-block rounded-full border border-[var(--aq-border)] bg-[var(--aq-panel)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-[var(--aq-cyan)]">
              AI chat · Private knowledge · Grounded research
            </p>
            <h1 id="aqlyra-home-heading" className="mt-7 text-4xl font-bold leading-tight tracking-tight sm:text-6xl">
              Aqlyra AI — <span className="text-[var(--aq-blue)]">think, search and explore</span> in one workspace.
            </h1>
            <p className="mt-7 max-w-2xl text-base leading-8 text-[var(--aq-muted)] sm:text-lg">
              Aqlyra brings AI conversation together with private document search,
              source-grounded answers and research tools. Ask questions, inspect
              references and keep your knowledge organized.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-3">
              <Link href="/login" className="rounded-xl bg-[var(--aq-blue)] px-6 py-3.5 text-sm font-semibold text-white transition hover:opacity-90">
                Open Aqlyra AI
              </Link>
              <Link href="/register" className="rounded-xl border border-[var(--aq-border)] bg-[var(--aq-panel)] px-6 py-3.5 text-sm font-semibold hover:border-[var(--aq-blue)]">
                Create an account
              </Link>
              <Link href="/demo" className="px-3 py-3.5 text-sm font-semibold text-[var(--aq-blue)] hover:underline">
                Explore public demo
              </Link>
            </div>
            <p className="mt-4 text-xs leading-6 text-[var(--aq-muted)]">
              The public demo contains scripted examples, not live AI responses.
              Features requiring external providers depend on service availability.
            </p>
          </div>
        </section>

        <section aria-labelledby="features-heading" className="border-t border-[var(--aq-border)] py-16">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--aq-cyan)]">What Aqlyra does</p>
          <h2 id="features-heading" className="mt-3 text-2xl font-bold sm:text-3xl">An AI workspace built around evidence</h2>
          <div className="mt-8 grid gap-4 sm:grid-cols-2">
            {features.map((feature) => (
              <article key={feature.title} className="rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-7">
                <span className="text-xs font-semibold text-[var(--aq-blue)]">{feature.label}</span>
                <h3 className="mt-3 text-lg font-semibold">{feature.title}</h3>
                <p className="mt-3 text-sm leading-7 text-[var(--aq-muted)]">{feature.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section aria-labelledby="grounded-heading" className="grid gap-8 border-t border-[var(--aq-border)] py-16 md:grid-cols-2 md:gap-16">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--aq-cyan)]">Why it matters</p>
            <h2 id="grounded-heading" className="mt-3 text-2xl font-bold sm:text-3xl">Answers you can check against sources</h2>
          </div>
          <div>
            <p className="text-sm leading-8 text-[var(--aq-muted)]">
              In Knowledge mode, Aqlyra can retrieve passages from selected documents
              and cite the evidence used in an answer. When sufficient evidence is
              unavailable, it can decline to answer. AI-generated results are not
              guaranteed correct; verify important facts against original sources.
            </p>
            <Link href="/how-it-works" className="mt-6 inline-block text-sm font-semibold text-[var(--aq-blue)] hover:underline">
              How Aqlyra RAG works
            </Link>
          </div>
        </section>

        <section className="my-10 rounded-3xl border border-[var(--aq-border)] bg-[var(--aq-panel)] px-6 py-12 sm:px-10" aria-labelledby="start-heading">
          <h2 id="start-heading" className="text-2xl font-bold">Ready to explore Aqlyra?</h2>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-[var(--aq-muted)]">
            Get started with the real workspace or browse the clearly labeled scripted walkthrough without an account.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href="/login" className="rounded-xl bg-[var(--aq-blue)] px-5 py-3 text-sm font-semibold text-white hover:opacity-90">Sign in to chat</Link>
            <Link href="/demo" className="rounded-xl border border-[var(--aq-border)] px-5 py-3 text-sm font-semibold hover:border-[var(--aq-blue)]">View demo</Link>
          </div>
        </section>

        <footer className="flex flex-wrap items-center justify-between gap-4 border-t border-[var(--aq-border)] py-8 text-xs text-[var(--aq-muted)]">
          <span>Aqlyra AI · Software under active development</span>
          <nav aria-label="Footer navigation" className="flex flex-wrap gap-5">
            <Link href="/about" className="hover:underline">About Aqlyra</Link>
            <Link href="/how-it-works" className="hover:underline">How RAG works</Link>
            <Link href="/help" className="hover:underline">Help and privacy guidance</Link>
            <Link href="/login" className="hover:underline">Sign in</Link>
          </nav>
        </footer>
      </div>
    </main>
  );
}
