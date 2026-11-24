import type { Metadata } from "next";
import Link from "next/link";

const origin = "https://aqlyra-ai.vercel.app";
const canonical = origin + "/rag-evaluation";
const description =
  "Explore Aqlyra AI's engineering evidence: document RAG architecture, multilingual semantic and keyword retrieval, citation checks, reproducible benchmarks, and limitations.";

export const metadata: Metadata = {
  title: "Aqlyra AI RAG Evaluation — Retrieval Quality & Limitations",
  description,
  alternates: { canonical },
  robots: { index: true, follow: true },
  openGraph: {
    type: "article",
    url: canonical,
    siteName: "Aqlyra AI",
    title: "Aqlyra AI — RAG Engineering Evidence and Evaluation",
    description,
  },
  twitter: {
    card: "summary",
    title: "Aqlyra AI — Document RAG Evaluation",
    description,
  },
};

const ciEvidence =
  "https://github.com/naim-munshi/aqlyra-rag-ai/actions/runs/42760735012";
const sourceRepository = "https://github.com/naim-munshi/aqlyra-rag-ai";

const structuredData = {
  "@context": "https://schema.org",
  "@type": "TechArticle",
  headline: "Aqlyra AI: RAG retrieval evaluation and engineering limitations",
  description,
  url: canonical,
  mainEntityOfPage: canonical,
  isPartOf: { "@id": origin + "/#website" },
  about: { "@id": origin + "/#software" },
  datePublished: "2026-11-13",
  inLanguage: "en",
  citation: [
    ciEvidence,
    sourceRepository + "/blob/release/core-without-study-abroad-20261027/backend/evaluation/REPRODUCIBLE_PROTOCOL.md",
  ],
};

export default function RagEvaluationPage() {
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
          <Link href="/" className="text-lg font-bold tracking-tight">Aqlyra AI</Link>
          <div className="flex flex-wrap items-center gap-5 text-sm">
            <Link href="/about" className="hover:underline">About</Link>
            <Link href="/how-it-works" className="hover:underline">How it works</Link>
            <Link href="/demo" className="text-[var(--aq-blue)] hover:underline">Demo</Link>
            <Link href="/login" className="hover:underline">Sign in</Link>
          </div>
        </nav>

        <header className="mt-16 max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--aq-blue)]">
            Public engineering notes · November 2026
          </p>
          <h1 className="mt-4 text-3xl font-bold leading-tight tracking-tight sm:text-5xl">
            Aqlyra AI: how we evaluate source-grounded document retrieval
          </h1>
          <p className="mt-6 text-base leading-8 text-[var(--aq-muted)]">
            Aqlyra is a multilingual AI workspace for general conversation and
            private document question answering. Its Knowledge workflow aims to
            retrieve authorized passages, answer with reviewable citations,
            and decline document-grounded claims that have insufficient evidence.
          </p>
          <p className="mt-4 text-sm leading-7 text-[var(--aq-muted)]">
            This page separates observed engineering evidence from unanswered
            product-quality questions. It does not claim that a synthetic
            benchmark proves real-user accuracy or that a model answer is always correct.
          </p>
        </header>

        <section className="mt-14" aria-labelledby="pipeline-heading">
          <h2 id="pipeline-heading" className="text-2xl font-bold">What the RAG pipeline does</h2>
          <ol className="mt-6 grid gap-4 sm:grid-cols-2">
            {[
              ["01 · Ingest", "Parse authorized files into passages with document and source-location metadata."],
              ["02 · Retrieve", "Use PostgreSQL lexical search and 384-dimensional semantic vectors when available. Combine candidates with rank fusion."],
              ["03 · Ground", "Select evidence under a context budget, generate an answer, and validate citation references."],
              ["04 · Refuse", "When the evidence does not support a requested document fact, return an explicit insufficient-evidence response instead of inventing a source."],
            ].map(([title, body]) => (
              <li key={title} className="rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-6">
                <h3 className="font-semibold">{title}</h3>
                <p className="mt-3 text-sm leading-7 text-[var(--aq-muted)]">{body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="mt-14 rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-6 sm:p-8" aria-labelledby="measurements-heading">
          <h2 id="measurements-heading" className="text-2xl font-bold">What has actually been measured</h2>
          <p className="mt-4 text-sm leading-7 text-[var(--aq-muted)]">
            The public engineering README reports that, on 10 November 2026,
            1,035 of 1,035 eligible production Knowledge chunks had matching
            384-dimensional embeddings; seven quarantined answer-key chunks
            were excluded. This measured indexing coverage, not the correctness
            of answers given to people.
          </p>
          <p className="mt-4 text-sm leading-7 text-[var(--aq-muted)]">
            A separate offline IBM Granite 97M R2 dense-retrieval experiment
            used 20 labeled English synthetic questions and 30 chunks.
            Its reported Hit Rate@1 was 90%, Hit Rate@3 was 100%, and MRR@5
            was 0.933. These figures are from that specific offline fixture,
            not independent real-world or multilingual performance claims.
          </p>
          <p className="mt-4 text-sm leading-7 text-[var(--aq-muted)]">
            <a href={ciEvidence} className="font-semibold text-[var(--aq-blue)] hover:underline" target="_blank" rel="noopener noreferrer">
              View the recorded benchmark workflow
            </a>
            {" · "}
            <a href={sourceRepository} className="font-semibold text-[var(--aq-blue)] hover:underline" target="_blank" rel="noopener noreferrer">
              Open the engineering repository
            </a>
          </p>
        </section>

        <section className="mt-14" aria-labelledby="limits-heading">
          <h2 id="limits-heading" className="text-2xl font-bold">Known limits and next experiments</h2>
          <div className="mt-6 space-y-5 text-sm leading-8 text-[var(--aq-muted)]">
            <p>
              <strong className="text-[var(--aq-text)]">Retrieval is not generation accuracy.</strong>{" "}
              A relevant passage can be retrieved and still be summarized incorrectly.
              Citation syntax does not guarantee that the cited paragraph supports a claim.
            </p>
            <p>
              <strong className="text-[var(--aq-text)]">Multilingual quality remains under evaluation.</strong>{" "}
              Japanese, Bengali and mixed-language examples need separately
              labeled retrieval and answer-quality tests. Remote semantic
              indexing, quotas and lexical fallbacks affect the result.
            </p>
            <p>
              <strong className="text-[var(--aq-text)]">A private document is not public search content.</strong>{" "}
              Tenant-scoped uploads and conversations are not published as SEO pages.
              Only these public, non-personal product and engineering explanations
              are intended for search-engine discovery.
            </p>
            <p>
              <strong className="text-[var(--aq-text)]">Research and voice availability may vary.</strong>{" "}
              Current public web research and live voice depend on configured
              third-party services, their quotas and actual deployment state.
            </p>
          </div>
        </section>

        <section className="mt-14 rounded-2xl border border-[var(--aq-border)] p-6">
          <h2 className="text-xl font-bold">Who is Aqlyra AI for?</h2>
          <p className="mt-3 text-sm leading-7 text-[var(--aq-muted)]">
            Aqlyra is being developed for people and teams who want to ask
            questions about selected documents and inspect the evidence used
            by an AI assistant. Typical pilot tasks include policy lookup,
            technical manual search, internal support knowledge and
            multilingual document questions. Enterprise readiness and
            business results require separate live-user validation.
          </p>
          <div className="mt-5 flex flex-wrap gap-5 text-sm font-semibold">
            <Link href="/demo" className="text-[var(--aq-blue)] hover:underline">Explore the scripted demo</Link>
            <Link href="/how-it-works" className="text-[var(--aq-blue)] hover:underline">Understand the RAG workflow</Link>
            <Link href="/about" className="text-[var(--aq-blue)] hover:underline">About Aqlyra AI</Link>
          </div>
        </section>
      </div>
    </main>
  );
}
