import type { Metadata } from "next";
import Link from "next/link";

const canonical = "https://aqlyra-ai.vercel.app/about";
const description =
  "Discover Aqlyra, an AI workspace for document search, source-grounded answers, citation-aware chat and research workflows. Explore the public demo.";

export const metadata: Metadata = {
  title: "About Aqlyra — AI Knowledge Workspace",
  description,
  alternates: { canonical },
  robots: { index: true, follow: true },
  openGraph: {
    type: "website",
    url: canonical,
    siteName: "Aqlyra",
    title: "Aqlyra — Source-Grounded AI Knowledge Workspace",
    description,
  },
  twitter: {
    card: "summary",
    title: "Aqlyra — AI Knowledge Workspace",
    description,
  },
};

const features = [
  {
    title: "Document search and grounded answers",
    description:
      "Work with selected documents and inspect source references when available. The Knowledge workflow can decline to answer when it cannot find enough evidence.",
  },
  {
    title: "AI conversation and research",
    description:
      "Use Converse for general conversation and explore optional web research workflows. Live answers depend on the configured services and their availability.",
  },
  {
    title: "Study Abroad planning",
    description:
      "Organize university research, compare entered academic facts with program criteria, and prepare application checklists. Results are planning assistance, not admission or visa decisions.",
  },
  {
    title: "Account-scoped documents and files",
    description:
      "Uploaded documents belong to your account. Aqlyra also includes tools to prepare downloadable files. Review any AI-generated output before using it.",
  },
] as const;

const structuredData = {
  "@context": "https://schema.org",
  "@type": "WebApplication",
  "@id": "https://aqlyra-ai.vercel.app/#software",
  name: "Aqlyra",
  url: "https://aqlyra-ai.vercel.app",
  description,
  applicationCategory: "BusinessApplication",
  operatingSystem: "Web",
  sameAs: "https://github.com/naim-munshi/aqlyra-rag-ai",
  featureList: features.map((feature) => feature.title),
};

export default function AboutPage() {
  return (
    <main className="min-h-screen bg-[var(--aq-bg)] px-5 py-9 text-[var(--aq-text)] sm:px-8">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(structuredData).replace(/</g, "\\u003c"),
        }}
      />
      <div className="mx-auto max-w-4xl">
        <nav aria-label="Public navigation" className="flex flex-wrap items-center justify-between gap-4">
          <Link href="/about" className="text-lg font-bold tracking-tight text-[var(--aq-text)]">
            Aqlyra
          </Link>
          <div className="flex flex-wrap items-center gap-5 text-sm">
            <Link href="/demo" className="text-[var(--aq-blue)] hover:underline">Explore demo</Link>
            <Link href="/how-it-works" className="hover:underline">How it works</Link>
            <Link href="/help" className="hover:underline">Help</Link>
            <Link href="/login" className="hover:underline">Sign in</Link>
          </div>
        </nav>

        <header className="mt-16 max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--aq-blue)]">
            Source-grounded knowledge AI
          </p>
          <h1 className="mt-4 text-3xl font-bold leading-tight tracking-tight sm:text-5xl">
            Meet Aqlyra, an AI workspace for your knowledge
          </h1>
          <p className="mt-6 text-base leading-8 text-[var(--aq-muted)]">
            Search documents, ask questions and explore research with citations
            and reviewable sources. Aqlyra brings conversation, private knowledge
            retrieval and practical planning tools into one workspace.
          </p>
          <div className="mt-8 flex flex-wrap gap-3 text-sm font-semibold">
            <Link href="/demo" className="rounded-xl bg-[var(--aq-blue)] px-5 py-3 text-white hover:opacity-90">
              Explore the scripted demo
            </Link>
            <Link href="/register" className="rounded-xl border border-[var(--aq-border)] px-5 py-3 hover:border-[var(--aq-blue)]">
              Create an account
            </Link>
          </div>
          <p className="mt-3 text-xs leading-6 text-[var(--aq-muted)]">
            The demo contains scripted examples, not live AI answers. Some
            features require an account and an available model provider.
          </p>
        </header>

        <section aria-labelledby="what-aqlyra-does" className="mt-16">
          <h2 id="what-aqlyra-does" className="text-2xl font-bold">What you can do with Aqlyra</h2>
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            {features.map((feature) => (
              <article key={feature.title} className="rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-6">
                <h3 className="text-lg font-semibold">{feature.title}</h3>
                <p className="mt-3 text-sm leading-7 text-[var(--aq-muted)]">{feature.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section aria-labelledby="how-it-works" className="mt-14 rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-6">
          <h2 id="how-it-works" className="text-xl font-semibold">How source-grounded answers work</h2>
          <p className="mt-3 text-sm leading-7 text-[var(--aq-muted)]">
            Documents are processed into searchable passages. When you use
            Knowledge, Aqlyra retrieves relevant passages and can attach
            citations to the answer. A citation points to evidence, but it does
            not guarantee that generated text is correct: verify important
            decisions against the original document or an official source.
          </p>
          <Link href="/how-it-works" className="mt-5 inline-block text-sm font-semibold text-[var(--aq-blue)] hover:underline">
            Read the full RAG and citation explanation
          </Link>
        </section>

        <footer className="mt-16 border-t border-[var(--aq-border)] py-7 text-sm text-[var(--aq-muted)]">
          Aqlyra is under active development. <Link href="/help" className="text-[var(--aq-blue)] hover:underline">Read help and privacy guidance</Link>.
        </footer>
      </div>
    </main>
  );
}
