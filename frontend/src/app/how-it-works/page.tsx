import type { Metadata } from "next";
import Link from "next/link";

const canonical = "https://aqlyra-ai.vercel.app/how-it-works";
const description =
  "How Aqlyra AI works: private document RAG, semantic and keyword retrieval, source citations, AI chat and optional current web research. Read its limits and see a scripted demo.";

export const metadata: Metadata = {
  title: "How Aqlyra Works — RAG, Document Search and AI Citations",
  description,
  alternates: { canonical },
  robots: { index: true, follow: true },
  openGraph: {
    type: "article",
    url: canonical,
    siteName: "Aqlyra",
    title: "How Aqlyra AI Works — Private RAG and Source-Grounded Answers",
    description,
  },
  twitter: {
    card: "summary",
    title: "How Aqlyra AI Works",
    description,
  },
};

const stages = [
  {
    title: "1. Prepare your documents",
    description:
      "The Knowledge workflow processes supported files into searchable passages. You choose which private documents to query; ingestion and indexing may take time.",
  },
  {
    title: "2. Retrieve relevant evidence",
    description:
      "Aqlyra combines keyword-based retrieval with semantic vector search when usable embeddings are available. When the semantic provider is unavailable or a document is not indexed, its lexical fallback can still find matching text.",
  },
  {
    title: "3. Generate a source-grounded answer",
    description:
      "A language model uses retrieved passages to draft an answer with references to the evidence. A citation is a way to inspect the source, not an independent guarantee that every statement is correct.",
  },
  {
    title: "4. Handle missing or changing information",
    description:
      "If selected documents lack sufficient evidence, Knowledge may decline to give a document-backed answer. For public, time-sensitive questions, optional web research can retrieve online sources when configured and available.",
  },
] as const;

const questions = [
  {
    question: "What is Aqlyra AI?",
    answer:
      "Aqlyra is a web-based AI workspace for conversation, searching selected private documents, reviewing cited answers and exploring public research. Its product is under active development.",
  },
  {
    question: "What does RAG mean in Aqlyra?",
    answer:
      "Retrieval-augmented generation (RAG) means looking up relevant passages from documents before asking an AI model to answer. Aqlyra's Knowledge mode is designed to show which document passages support an answer.",
  },
  {
    question: "Does Aqlyra use current web information automatically?",
    answer:
      "For some time-sensitive public questions, Aqlyra can select Web Research automatically. Actual freshness, coverage and availability depend on its search provider and the websites retrieved; it cannot guarantee real-time correctness.",
  },
  {
    question: "Are uploaded documents public or searchable on Google?",
    answer:
      "No. Personal documents and their retrieved passages are account-scoped inside the application. Public marketing and help pages can be indexed; private workspace pages are not intended for search-engine indexing.",
  },
  {
    question: "Is the Aqlyra demo a live AI response?",
    answer:
      "No. The public demo is an explicitly scripted walkthrough. Live chat and document tools depend on account access and available backend/model services.",
  },
  {
    question: "Does a citation guarantee that an AI answer is correct?",
    answer:
      "No. Citations make the evidence reviewable, but important facts should still be verified against original documents or authoritative sources.",
  },
] as const;

export default function HowItWorksPage() {
  return (
    <main className="min-h-screen bg-[var(--aq-bg)] px-5 py-9 text-[var(--aq-text)] sm:px-8">
      <div className="mx-auto max-w-4xl">
        <nav aria-label="Public navigation" className="flex flex-wrap items-center justify-between gap-4">
          <Link href="/" className="text-lg font-bold">Aqlyra AI</Link>
          <div className="flex flex-wrap items-center gap-5 text-sm">
            <Link href="/about" className="hover:underline">About</Link>
            <Link href="/demo" className="text-[var(--aq-blue)] hover:underline">Demo</Link>
            <Link href="/help" className="hover:underline">Help</Link>
          </div>
        </nav>

        <header className="mt-16 max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--aq-blue)]">
            Technology and transparent product information
          </p>
          <h1 className="mt-4 text-3xl font-bold leading-tight sm:text-5xl">
            How Aqlyra AI works: document RAG, citations and web research
          </h1>
          <p className="mt-6 text-base leading-8 text-[var(--aq-muted)]">
            Aqlyra combines AI chat with retrieval-augmented generation (RAG)
            for private documents. Rather than presenting every model answer as
            a verified fact, its Knowledge workflow retrieves evidence, attaches
            source references when possible and can decline unsupported answers.
          </p>
          <div className="mt-8 flex flex-wrap gap-4 text-sm font-semibold">
            <Link href="/demo" className="rounded-xl bg-[var(--aq-blue)] px-5 py-3 text-white hover:opacity-90">
              Explore the scripted demo
            </Link>
            <Link href="/about" className="rounded-xl border border-[var(--aq-border)] px-5 py-3 hover:border-[var(--aq-blue)]">
              About Aqlyra
            </Link>
          </div>
        </header>

        <section aria-labelledby="rag-stages" className="mt-16">
          <h2 id="rag-stages" className="text-2xl font-bold">How document retrieval works</h2>
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            {stages.map((stage) => (
              <article key={stage.title} className="rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-6">
                <h3 className="text-lg font-semibold">{stage.title}</h3>
                <p className="mt-3 text-sm leading-7 text-[var(--aq-muted)]">{stage.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section aria-labelledby="product-modes" className="mt-16">
          <h2 id="product-modes" className="text-2xl font-bold">Aqlyra Converse, Knowledge and Web Research</h2>
          <div className="mt-4 space-y-4 text-sm leading-8 text-[var(--aq-muted)]">
            <p><strong className="text-[var(--aq-text)]">Converse:</strong> general AI conversation for drafting and exploring ideas. General model outputs may be inaccurate and are not automatically verified against documents.</p>
            <p><strong className="text-[var(--aq-text)]">Knowledge:</strong> answers using selected, account-scoped documents with semantic search when indexed and lexical retrieval when needed.</p>
            <p><strong className="text-[var(--aq-text)]">Web Research:</strong> a separate, source-oriented path for public questions such as recent news and changing facts. Research depends on available search and AI providers and should not be mistaken for an always-live database.</p>
          </div>
        </section>

        <section aria-labelledby="common-questions" className="mt-16">
          <h2 id="common-questions" className="text-2xl font-bold">Frequently asked questions about Aqlyra</h2>
          <div className="mt-5 space-y-5">
            {questions.map(({ question, answer }) => (
              <section key={question} className="border-b border-[var(--aq-border)] pb-5">
                <h3 className="text-lg font-semibold">{question}</h3>
                <p className="mt-2 text-sm leading-7 text-[var(--aq-muted)]">{answer}</p>
              </section>
            ))}
          </div>
        </section>

        <aside className="mt-14 rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-6">
          <h2 className="text-lg font-bold">Limitations and privacy</h2>
          <p className="mt-3 text-sm leading-7 text-[var(--aq-muted)]">
            Aqlyra is a production beta, not a source of guaranteed medical,
            legal, financial or admissions advice. Retrieval coverage, live
            model capacity and document/file availability can vary. Documents
            are not public web pages; use the application only with material
            you are authorized to share with its configured service providers.
          </p>
          <Link href="/help" className="mt-4 inline-block text-sm font-semibold text-[var(--aq-blue)] hover:underline">
            Read the help and privacy guidance
          </Link>
          <p className="mt-3 text-sm text-[var(--aq-muted)]">
            For code, architecture and technical limitations, see the{" "}
            <a href="https://github.com/naim-munshi/aqlyra-rag-ai" target="_blank" rel="noopener noreferrer" className="text-[var(--aq-blue)] hover:underline">public engineering repository</a>.
          </p>
        </aside>

        <footer className="mt-14 border-t border-[var(--aq-border)] py-8 text-sm text-[var(--aq-muted)]">
          Read more <Link href="/about" className="text-[var(--aq-blue)] hover:underline">about Aqlyra</Link>,
          explore the <Link href="/demo" className="text-[var(--aq-blue)] hover:underline">public demo</Link>, or
          <Link href="/" className="ml-1 text-[var(--aq-blue)] hover:underline">open Aqlyra AI</Link>.
        </footer>
      </div>
    </main>
  );
}
