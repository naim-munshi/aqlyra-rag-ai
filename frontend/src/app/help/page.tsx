import Link from "next/link";

const topics = [
  {
    heading: "Converse and Knowledge",
    text: "Converse is for general AI conversation. Knowledge answers from your selected indexed documents. Verified sources may be cited, and unsupported document questions can be refused.",
  },
  {
    heading: "Upload and search your documents",
    text: "Use Documents in the workspace to upload supported PDF, Word, PowerPoint, Excel, text and image files. Allow processing to finish before selecting them in Knowledge.",
  },
  {
    heading: "AI Files",
    text: "Create real Word, Excel, PowerPoint, PDF or Markdown files. Download, edit the underlying text or save a new version. You must opt in before selected private-document excerpts are shared with a configured AI provider.",
  },
  {
    heading: "Privacy and safety",
    text: "Your documents are account-scoped. Treat AI output as research assistance rather than guaranteed professional advice. Avoid uploading secrets you do not want the configured model provider to process.",
  },
];

export default function HelpPage() {
  return (
    <main className="min-h-screen bg-[var(--aq-bg)] px-5 py-8 text-[var(--aq-text)] sm:px-8">
      <div className="mx-auto max-w-3xl">
        <Link href="/" className="text-sm text-[var(--aq-blue)] hover:underline">
          Back to Aqlyra
        </Link>
        <h1 className="mt-5 text-3xl font-bold">Aqlyra Help</h1>
        <p className="mt-3 text-sm leading-7 text-[var(--aq-muted)]">
          Getting started with your private AI workspace. Features that require
          a live AI provider may be unavailable in demo or local test mode.
        </p>
        <div className="mt-7 space-y-4">
          {topics.map((topic) => (
            <section
              key={topic.heading}
              className="rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-5"
            >
              <h2 className="font-semibold">{topic.heading}</h2>
              <p className="mt-2 text-sm leading-7 text-[var(--aq-muted)]">
                {topic.text}
              </p>
            </section>
          ))}
        </div>
        <p className="mt-7 text-sm text-[var(--aq-muted)]">
          Aqlyra is under active development. Paid subscriptions are not available.
          For project-level technical information, see the repository documentation.
        </p>
      </div>
    </main>
  );
}
