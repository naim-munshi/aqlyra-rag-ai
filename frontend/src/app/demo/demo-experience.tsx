"use client";

import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpenText,
  Check,
  ChevronRight,
  CircleDot,
  Code2,
  Copy,
  Database,
  FileSearch,
  Fingerprint,
  GitBranch,
  Layers3,
  LockKeyhole,
  MessageSquareText,
  Network,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  WandSparkles,
} from "lucide-react";
import { type FormEvent, useState } from "react";

import { AqlyraLogo } from "@/components/brand/aqlyra-logo";
import {
  findScenario,
  previewScenarios,
  scenariosForMode,
  type PreviewMode,
} from "@/lib/demo/scenarios";

import styles from "./demo.module.css";

type PreviewSection = "workspace" | "architecture";

const stages = [
  {
    number: "01",
    title: "Ingest",
    description: "Parse documents and split source text into searchable chunks.",
    icon: FileSearch,
  },
  {
    number: "02",
    title: "Retrieve",
    description: "Combine semantic and lexical search, then rank candidate evidence.",
    icon: Search,
  },
  {
    number: "03",
    title: "Ground",
    description: "Generate responses, validate source references, and refuse weak claims.",
    icon: ShieldCheck,
  },
] as const;

const architecture = [
  {
    icon: Layers3,
    label: "Interface",
    name: "Next.js · React · TypeScript",
    detail: "Converse, Knowledge, verified session and project workflows.",
  },
  {
    icon: Network,
    label: "Application",
    name: "FastAPI · Python",
    detail: "Authenticated APIs, retrieval orchestration and streamed responses.",
  },
  {
    icon: Database,
    label: "Data",
    name: "PostgreSQL · pgvector · Redis",
    detail: "Document vectors, conversation persistence and rate limiting.",
  },
  {
    icon: Fingerprint,
    label: "Security",
    name: "JWT · ownership checks",
    detail: "Email verification, user-scoped resources and adversarial testing.",
  },
] as const;

export function DemoExperience() {
  const demoOnly = process.env.NEXT_PUBLIC_AQLYRA_DEMO_ONLY === "true";
  const [section, setSection] = useState<PreviewSection>("workspace");
  const [mode, setMode] = useState<PreviewMode>("knowledge");
  const [selectedId, setSelectedId] = useState("access");
  const [question, setQuestion] = useState("");
  const [feedback, setFeedback] = useState("");
  const [showEvidence, setShowEvidence] = useState(true);
  const [copied, setCopied] = useState(false);

  const selected = findScenario(selectedId) ?? previewScenarios[0];
  const available = scenariosForMode(mode);

  function selectMode(nextMode: PreviewMode) {
    setMode(nextMode);
    setSelectedId(nextMode === "knowledge" ? "access" : "explain");
    setQuestion("");
    setFeedback("");
    setCopied(false);
    setShowEvidence(true);
    setSection("workspace");
  }

  function runExample(id: string) {
    const scenario = findScenario(id);
    if (!scenario) {
      return;
    }

    setMode(scenario.mode);
    setSelectedId(id);
    setQuestion(scenario.prompt);
    setFeedback("");
    setCopied(false);
    setShowEvidence(true);
    setSection("workspace");
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = question.trim().toLowerCase();

    if (!normalized) {
      setFeedback("Choose a suggested question to explore the sample workflow.");
      return;
    }

    const matched = previewScenarios.find(
      (scenario) => scenario.prompt.toLowerCase() === normalized,
    );

    if (!matched) {
      setFeedback(
        "This preview uses scripted examples. Select a suggested prompt to see a complete walkthrough; live AI is available only when the backend is deployed.",
      );
      return;
    }

    runExample(matched.id);
  }

  async function copyAnswer() {
    if (!selected) {
      return;
    }

    try {
      await navigator.clipboard.writeText(selected.answer);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setFeedback("Copy was unavailable in this browser. Select the sample answer to copy it.");
    }
  }

  return (
    <main className={styles.shell}>
      <div aria-hidden="true" className={styles.backgroundGlow} />

      <aside className={styles.sidebar} aria-label="Aqlyra demo navigation">
        <div className={styles.brandBlock}>
          <AqlyraLogo size={42} />
          <span className={styles.edition}>ENGINEERING PREVIEW</span>
        </div>

        <div className={styles.sidebarGroup}>
          <span className={styles.sidebarLabel}>EXPLORE</span>
          <button
            type="button"
            aria-current={section === "workspace" ? "page" : undefined}
            className={section === "workspace" ? styles.sidebarActive : styles.sidebarItem}
            onClick={() => setSection("workspace")}
          >
            <MessageSquareText size={17} strokeWidth={1.8} />
            Product walkthrough
            <ChevronRight size={15} className={styles.navArrow} />
          </button>
          <button
            type="button"
            aria-current={section === "architecture" ? "page" : undefined}
            className={section === "architecture" ? styles.sidebarActive : styles.sidebarItem}
            onClick={() => setSection("architecture")}
          >
            <Network size={17} strokeWidth={1.8} />
            System architecture
            <ChevronRight size={15} className={styles.navArrow} />
          </button>
        </div>

        <div className={styles.sidebarGroup}>
          <span className={styles.sidebarLabel}>PRODUCT MODES</span>
          <button
            type="button"
            className={section === "workspace" && mode === "knowledge" ? styles.modeSelected : styles.modeItem}
            onClick={() => selectMode("knowledge")}
          >
            <BookOpenText size={17} strokeWidth={1.8} />
            Knowledge
            <span className={styles.modeMark}>RAG</span>
          </button>
          <button
            type="button"
            className={section === "workspace" && mode === "converse" ? styles.modeSelected : styles.modeItem}
            onClick={() => selectMode("converse")}
          >
            <Sparkles size={17} strokeWidth={1.8} />
            Converse
          </button>
        </div>

        <div className={styles.sidebarSpacer} />

        <div className={styles.sidebarNote}>
          <span className={styles.sidebarNoteIcon}><ShieldCheck size={16} /></span>
          <strong>Designed for trust</strong>
          <p>Verified identities, source-aware answers and private knowledge workflows.</p>
          <button type="button" onClick={() => setSection("architecture")} className={styles.sidebarNoteFoot}>Explore the architecture <ArrowUpRight size={12} /></button>
        </div>

        <a
          className={styles.sidebarGithub}
          href="https://github.com/naim-munshi/aqlyra-rag-ai"
          target="_blank"
          rel="noopener noreferrer"
        >
          <GitBranch size={17} /> View source on GitHub <ArrowUpRight size={14} />
        </a>
      </aside>

      <div className={styles.mainArea}>
        <header className={styles.topbar}>
          <div className={styles.breadcrumb}>
            <span className={styles.breadcrumbMuted}>AQLYRA</span>
            <ChevronRight size={13} />
            <span>{section === "workspace" ? "Product preview" : "Engineering"}</span>
          </div>
          <div className={styles.topbarActions}>
            <span className={styles.previewBadge}><span /> PUBLIC DEMO</span>
            {demoOnly ? (
              <a
                href="https://github.com/naim-munshi/aqlyra-rag-ai"
                target="_blank"
                rel="noopener noreferrer"
                className={styles.signInLink}
              >
                View source <ArrowUpRight size={14} />
              </a>
            ) : (
              <Link href="/login" className={styles.signInLink}>
                Sign in <ArrowUpRight size={14} />
              </Link>
            )}
          </div>
        </header>

        <div className={styles.mobileTabs} aria-label="Demo sections">
          <button
            type="button"
            className={section === "workspace" ? styles.mobileActive : ""}
            onClick={() => setSection("workspace")}
          >
            Workspace
          </button>
          <button
            type="button"
            className={section === "architecture" ? styles.mobileActive : ""}
            onClick={() => setSection("architecture")}
          >
            Architecture
          </button>
        </div>

        {section === "workspace" ? (
          <div className={styles.content}>
            <section className={styles.hero} aria-labelledby="demo-heading">
              <div className={styles.heroEyebrow}>
                <span className={styles.eyebrowLine} />
                DOCUMENT INTELLIGENCE, MADE TRACEABLE
              </div>
              <h1 id="demo-heading">
                Intelligence you can <span>trace.</span>
              </h1>
              <p>
                Explore how Aqlyra connects questions to knowledge, surfaces the
                evidence behind an answer, and keeps source context in view.
              </p>
              <div className={styles.heroActions}>
                {!demoOnly ? (
                  <Link href="/login" className={styles.primaryButton}>
                    <ArrowRight size={17} /> Try the real AI app
                  </Link>
                ) : null}
                <button
                  type="button"
                  className={styles.primaryButton}
                  onClick={() => runExample("access")}
                >
                  <WandSparkles size={17} /> Explore the walkthrough <ArrowRight size={16} />
                </button>
                <button
                  type="button"
                  className={styles.secondaryButton}
                  onClick={() => setSection("architecture")}
                >
                  View architecture <ArrowUpRight size={15} />
                </button>
              </div>
              <div className={styles.heroOrbit} aria-hidden="true">
                <span className={styles.orbitOuter} />
                <span className={styles.orbitInner} />
                <span className={styles.orbitCore}><Layers3 size={27} strokeWidth={1.5} /></span>
                <span className={styles.orbitDot} />
              </div>
            </section>

            <section className={styles.stats} aria-label="Preview capabilities">
              <div className={styles.stat}>
                <div><span className={styles.statNumber}>02</span><span className={styles.statAccent}> / MODE</span></div>
                <p>Converse & Knowledge</p>
              </div>
              <div className={styles.stat}>
                <div><span className={styles.statNumber}>03</span><span className={styles.statAccent}> / STEPS</span></div>
                <p>Ingest → Retrieve → Ground</p>
              </div>
              <div className={styles.stat}>
                <div><span className={styles.statNumber}>05</span><span className={styles.statAccent}> / EXAMPLES</span></div>
                <p>Interactive sample prompts</p>
              </div>
            </section>

            <section className={styles.workbench} aria-labelledby="workbench-heading">
              <div className={styles.workbenchHeader}>
                <div>
                  <div className={styles.sectionEyebrow}>INTERACTIVE WORKSPACE</div>
                  <h2 id="workbench-heading">See the workflow in action</h2>
                  <p>Click a prompt to inspect an illustrative response and its context.</p>
                </div>
                <span className={styles.mockBadge}><CircleDot size={13} /> SIMULATED CONTENT</span>
              </div>

              <div className={styles.modeTabs} role="group" aria-label="Example mode">
                <button
                  type="button"
                  aria-pressed={mode === "knowledge"}
                  onClick={() => selectMode("knowledge")}
                  className={mode === "knowledge" ? styles.tabActive : styles.tab}
                >
                  <BookOpenText size={16} /> Knowledge
                </button>
                <button
                  type="button"
                  aria-pressed={mode === "converse"}
                  onClick={() => selectMode("converse")}
                  className={mode === "converse" ? styles.tabActive : styles.tab}
                >
                  <MessageSquareText size={16} /> Converse
                </button>
              </div>

              <div className={styles.workbenchGrid}>
                <div className={styles.promptSide}>
                  <div className={styles.panelHeading}>
                    <span>01 / SELECT A QUESTION</span>
                    <span className={styles.panelLabel}>{available.length} SAMPLES</span>
                  </div>
                  <div className={styles.promptChoices}>
                    {available.map((scenario) => (
                      <button
                        key={scenario.id}
                        type="button"
                        aria-pressed={selected.id === scenario.id}
                        className={selected.id === scenario.id ? styles.promptActive : styles.promptChoice}
                        onClick={() => runExample(scenario.id)}
                      >
                        <span className={styles.promptIcon}><Search size={16} /></span>
                        <span className={styles.promptText}>
                          <strong>{scenario.title}</strong>
                          <small>{scenario.prompt}</small>
                        </span>
                        <ArrowUpRight size={15} className={styles.promptArrow} />
                      </button>
                    ))}
                  </div>

                  <form className={styles.askForm} onSubmit={handleSubmit}>
                    <label htmlFor="demo-question">Try a sample prompt</label>
                    <div className={styles.inputRow}>
                      <input
                        id="demo-question"
                        value={question}
                        onChange={(event) => {
                          setQuestion(event.target.value);
                          setFeedback("");
                        }}
                        placeholder="Choose a prompt above..."
                        autoComplete="off"
                      />
                      <button aria-label="Show sample answer" type="submit"><Send size={17} /></button>
                    </div>
                    {feedback ? (
                      <p className={styles.formFeedback} role="status">{feedback}</p>
                    ) : (
                      <p className={styles.inputFootnote}>Demo prompts only. No backend requests or user data storage.</p>
                    )}
                  </form>
                </div>

                <div className={styles.answerSide} aria-live="polite">
                  <div className={styles.panelHeading}>
                    <span>02 / EXPLORE THE RESPONSE</span>
                    <span className={styles.panelLabel}><span className={styles.accentDot} /> EXAMPLE</span>
                  </div>

                  <div className={styles.sampleQuestion}>
                    <span className={styles.smallAvatar}>YOU</span>
                    <p>{selected.prompt}</p>
                  </div>
                  <div className={styles.sampleAnswer}>
                    <div className={styles.aiHeader}>
                      <span className={styles.aiAvatar}><Sparkles size={17} /></span>
                      <div><strong>Aqlyra</strong><small>Illustrative sample response</small></div>
                      <button
                        type="button"
                        onClick={() => void copyAnswer()}
                        className={styles.copyButton}
                        aria-label="Copy example answer"
                      >
                        {copied ? <Check size={16} /> : <Copy size={16} />}
                        <span>{copied ? "Copied" : "Copy"}</span>
                      </button>
                    </div>
                    <p className={styles.answerText}>{selected.answer}</p>

                    <div className={styles.answerFooter}>
                      <span><ShieldCheck size={15} /> {selected.mode === "knowledge" ? "Evidence-linked example" : "Scripted conversation example"}</span>
                      {selected.sourceExcerpt && (
                        <button
                          type="button"
                          onClick={() => setShowEvidence((current) => !current)}
                          aria-expanded={showEvidence}
                        >
                          {showEvidence ? "Hide evidence" : "Inspect evidence"} <ChevronRight size={14} />
                        </button>
                      )}
                    </div>
                  </div>

                  {selected.sourceExcerpt && showEvidence && (
                    <div className={styles.evidenceCard}>
                      <div className={styles.evidenceHeader}>
                        <span className={styles.sourceTag}>S1</span>
                        <div>
                          <strong>{selected.fileName}</strong>
                          <small>{selected.sourceHeading} · illustrative excerpt</small>
                        </div>
                        <FileSearch size={18} className={styles.sourceIcon} />
                      </div>
                      <blockquote>{selected.sourceExcerpt}</blockquote>
                      <div className={styles.evidenceFoot}>
                        <Check size={14} /> {selected.reasoningNote}
                      </div>
                    </div>
                  )}

                  {selected.mode === "converse" && (
                    <div className={styles.converseNote}>
                      <MessageSquareText size={18} />
                      <p>{selected.reasoningNote}</p>
                    </div>
                  )}
                </div>
              </div>
            </section>

            <section className={styles.featureTour} aria-labelledby="capability-heading">
              <div className={styles.sectionEyebrow}>REAL APPLICATION VS SCRIPTED DEMO</div>
              <h2 id="capability-heading">Explore every major workflow</h2>
              <p className={styles.featureTourIntro}>
                This page displays scripted samples only. The live workflows below
                require the real app, authentication and available providers.
                Not every advanced feature is currently enabled.
              </p>
              <div className={styles.featureGrid}>
                <article className={styles.featureCard}>
                  <span className={styles.featureStatus}>LIVE BETA</span>
                  <h3>Converse &amp; memory</h3>
                  <p>Ask, follow up, attach permitted files and inspect user-scoped conversations.</p>
                </article>
                <article className={styles.featureCard}>
                  <span className={styles.featureStatus}>LIVE BETA</span>
                  <h3>Knowledge RAG</h3>
                  <p>Upload a sample document; test semantic + lexical retrieval and source citations.</p>
                </article>
                <article className={styles.featureCard}>
                  <span className={styles.featureStatus}>PROVIDER LIVE</span>
                  <h3>Web Research</h3>
                  <p>Tavily supplies current public sources. Independent search has a limited fallback only.</p>
                </article>
                <article className={styles.featureCard}>
                  <span className={styles.featureStatus}>BROWSER DEPENDENT</span>
                  <h3>Voice</h3>
                  <p>Speech recognition/playback fallback may work with permission. LiveKit RTC is not certified.</p>
                </article>
                <article className={styles.featureCard}>
                  <span className={styles.featureStatusRestricted}>SAFETY-GATED</span>
                  <h3>Browser Agent</h3>
                  <p>Production execution remains off until isolated runtime and egress controls are accepted.</p>
                </article>
                <article className={styles.featureCard}>
                  <span className={styles.featureStatusRestricted}>LIMITED CANARY</span>
                  <h3>Own Hybrid Search</h3>
                  <p>Token-protected SearXNG has a Wikipedia-backed probe; not a replacement for broad web search.</p>
                </article>
              </div>
              <div className={styles.heroActions}>
                {demoOnly ? (
                  <a href="https://github.com/naim-munshi/aqlyra-rag-ai/blob/release/core-without-study-abroad-20261027/docs/PRODUCT_DEMO_AND_ACCEPTANCE.md"
                    className={styles.secondaryButton} target="_blank" rel="noopener noreferrer">
                    Read acceptance steps <ArrowUpRight size={15}/>
                  </a>
                ) : (
                  <Link href="/login" className={styles.secondaryButton}>
                    Open real sign-in <ArrowUpRight size={15}/>
                  </Link>
                )}
              </div>
            </section>

            <section className={styles.method} aria-labelledby="method-heading">
              <div className={styles.methodTitle}>
                <div><div className={styles.sectionEyebrow}>UNDER THE HOOD</div>
                  <h2 id="method-heading">Evidence-first by design.</h2>
                </div>
                <button type="button" onClick={() => setSection("architecture")}>
                  Full architecture <ArrowUpRight size={15} />
                </button>
              </div>
              <div className={styles.pipeline}>
                {stages.map(({ number, title, description, icon: Icon }) => (
                  <div className={styles.pipelineCard} key={number}>
                    <div className={styles.pipelineHead}>
                      <span>{number}</span><Icon size={19} strokeWidth={1.7} />
                    </div>
                    <h3>{title}</h3>
                    <p>{description}</p>
                  </div>
                ))}
              </div>
            </section>

            <footer className={styles.footer}>
              <span>© Aqlyra · An AI engineering portfolio project</span>
              <span>Public preview · Scripted examples · No live inference</span>
            </footer>
          </div>
        ) : (
          <div className={styles.content}>
            <section className={styles.archHero}>
              <div className={styles.heroEyebrow}><span className={styles.eyebrowLine} /> BUILT TO BE EXPLAINABLE</div>
              <h1>The engineering <span>behind Aqlyra.</span></h1>
              <p>
                A separated application stack with retrieval, authorization,
                monitoring and deployment controls. Explore the real repository
                for implementation details and automated test evidence.
              </p>
              <a
                href="https://github.com/naim-munshi/aqlyra-rag-ai"
                target="_blank"
                rel="noopener noreferrer"
                className={styles.primaryButton}
              >
                <GitBranch size={17} /> Explore the source <ArrowUpRight size={16} />
              </a>
            </section>

            <div className={styles.archHeader}>
              <div className={styles.sectionEyebrow}>SYSTEM COMPONENTS</div>
              <h2>Purpose-built layers</h2>
              <p>Implemented in the repository; availability depends on deployment configuration.</p>
            </div>
            <div className={styles.archGrid}>
              {architecture.map(({ icon: Icon, label, name, detail }) => (
                <article className={styles.archCard} key={name}>
                  <span className={styles.archIcon}><Icon size={21} strokeWidth={1.7} /></span>
                  <div className={styles.sectionEyebrow}>{label}</div>
                  <h3>{name}</h3>
                  <p>{detail}</p>
                  <span className={styles.archCardFoot}>SOURCE AVAILABLE <ArrowUpRight size={14} /></span>
                </article>
              ))}
            </div>

            <section className={styles.engineeringNote}>
              <div className={styles.engineeringNoteIcon}><Code2 size={21} /></div>
              <div>
                <h2>What is live in this preview?</h2>
                <p>
                  This page runs entirely in the browser using authored sample
                  scenarios. It does not authenticate accounts, index files,
                  call an LLM, or query PostgreSQL. Backend functionality and
                  automated tests remain in the source repository.
                </p>
              </div>
              {demoOnly ? (
                <a
                  href="https://github.com/naim-munshi/aqlyra-rag-ai"
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.secondaryButton}
                >
                  Review source <ArrowUpRight size={15} />
                </a>
              ) : (
                <Link href="/login" className={styles.secondaryButton}>
                  App sign in <ArrowUpRight size={15} />
                </Link>
              )}
            </section>

            <div className={styles.archActions}>
              <button type="button" className={styles.secondaryButton} onClick={() => setSection("workspace")}>
                <ArrowRight size={16} /> Return to demo
              </button>
              <a
                href="https://github.com/naim-munshi/aqlyra-rag-ai/actions"
                target="_blank"
                rel="noopener noreferrer"
                className={styles.ciLink}
              >
                <LockKeyhole size={16} /> GitHub CI evidence <ArrowUpRight size={15} />
              </a>
            </div>

            <footer className={styles.footer}>
              <span>© Aqlyra · An AI engineering portfolio project</span>
              <span>Public preview · No live provider calls</span>
            </footer>
          </div>
        )}
      </div>
    </main>
  );
}
