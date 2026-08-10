"use client";

import {
  AlertCircle,
  Copy,
  FileSearch,
  LoaderCircle,
  Mic,
  Paperclip,
  Send,
  Sparkles,
} from "lucide-react";
import {
  FormEvent,
  useMemo,
  useState,
} from "react";

import type {
  RAGAnswerResponse,
  RAGCitationResponse,
  RAGErrorResponse,
} from "@/types/rag";

function getErrorMessage(
  data: RAGErrorResponse | null,
) {
  if (!data) {
    return "Unable to get a grounded answer.";
  }

  if (typeof data.detail === "string") {
    return data.detail;
  }

  if (Array.isArray(data.detail)) {
    return (
      data.detail[0]?.msg ??
      "Unable to get a grounded answer."
    );
  }

  return "Unable to get a grounded answer.";
}

function formatSimilarity(score: number) {
  return score.toFixed(3);
}

export function RAGWorkspace() {
  const [question, setQuestion] = useState("");
  const [result, setResult] =
    useState<RAGAnswerResponse | null>(null);

  const [selectedCitationId, setSelectedCitationId] =
    useState<string | null>(null);

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState("");

  const selectedCitation =
    useMemo<RAGCitationResponse | null>(() => {
      if (!result?.citations.length) {
        return null;
      }

      if (!selectedCitationId) {
        return result.citations[0];
      }

      return (
        result.citations.find(
          (citation) =>
            citation.source_id ===
            selectedCitationId,
        ) ?? result.citations[0]
      );
    }, [
      result,
      selectedCitationId,
    ]);

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    const cleanedQuestion =
      question.trim();

    if (!cleanedQuestion || loading) {
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);
    setSelectedCitationId(null);

    try {
      const response = await fetch(
        "/api/rag/answer",
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            question: cleanedQuestion,
          }),
        },
      );

      const data =
        (await response.json()) as
          | RAGAnswerResponse
          | RAGErrorResponse;

      if (!response.ok) {
        setError(
          getErrorMessage(
            data as RAGErrorResponse,
          ),
        );

        return;
      }

      const answer =
        data as RAGAnswerResponse;

      setResult(answer);

      if (answer.citations.length > 0) {
        setSelectedCitationId(
          answer.citations[0].source_id,
        );
      }
    } catch {
      setError(
        "Unable to connect to the RAG service.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function copyAnswer() {
    if (!result?.answer) {
      return;
    }

    await navigator.clipboard.writeText(
      result.answer,
    );
  }

  async function copyEvidence() {
    if (!selectedCitation?.excerpt) {
      return;
    }

    await navigator.clipboard.writeText(
      selectedCitation.excerpt,
    );
  }

  return (
    <>
      {/* Chat */}
      <section className="aq-panel flex min-h-0 flex-col bg-[var(--aq-panel-strong)]">
        <div className="flex h-14 shrink-0 items-center justify-between border-b border-[var(--aq-border)] px-5">
          <div className="flex items-center gap-2">
            <Sparkles
              size={17}
              className="text-[var(--aq-cyan)]"
            />

            <h2 className="text-sm font-semibold">
              Aqlyra RAG
            </h2>
          </div>

          <span className="text-[10px] font-semibold text-[var(--aq-success)]">
            Grounded mode
          </span>
        </div>

        <div className="aq-scrollbar min-h-0 flex-1 overflow-y-auto p-6">
          {!result && !loading && !error && (
            <div className="flex h-full min-h-[320px] items-center justify-center text-center">
              <div className="max-w-[430px]">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-card)] text-[var(--aq-blue)]">
                  <Sparkles size={23} />
                </div>

                <h2 className="mt-5 text-lg font-semibold">
                  Ask Aqlyra about your documents
                </h2>

                <p className="mt-2 text-sm leading-6 text-[var(--aq-muted)]">
                  Ask a question and Aqlyra will
                  retrieve evidence from your processed
                  documents and return grounded sources.
                </p>
              </div>
            </div>
          )}

          {loading && (
            <div className="flex h-full min-h-[320px] items-center justify-center">
              <div className="text-center">
                <LoaderCircle
                  size={28}
                  className="mx-auto animate-spin text-[var(--aq-blue)]"
                />

                <p className="mt-4 text-sm font-semibold">
                  Retrieving evidence...
                </p>

                <p className="mt-2 text-xs text-[var(--aq-muted)]">
                  Aqlyra is searching your
                  knowledge base.
                </p>
              </div>
            </div>
          )}

          {error && (
            <div className="mx-auto mt-12 max-w-[520px] rounded-2xl border border-red-500/30 bg-red-500/10 p-5">
              <div className="flex gap-3">
                <AlertCircle
                  size={18}
                  className="mt-0.5 shrink-0 text-red-400"
                />

                <div>
                  <p className="text-sm font-semibold text-red-400">
                    RAG request failed
                  </p>

                  <p className="mt-2 text-xs leading-5 text-red-300">
                    {error}
                  </p>
                </div>
              </div>
            </div>
          )}

          {result && (
            <div>
              <div className="ml-auto max-w-[460px] rounded-2xl border border-[var(--aq-blue)] bg-[var(--aq-blue-soft)] px-5 py-4 text-sm leading-6">
                {result.question}
              </div>

              <div className="mt-8">
                <div className="mb-3 flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--aq-blue)] bg-[var(--aq-card)] text-xs font-bold text-[var(--aq-cyan)]">
                    AQ
                  </div>

                  <span className="text-xs font-semibold">
                    Aqlyra
                  </span>

                  <span className="text-[10px] font-semibold text-[var(--aq-success)]">
                    {result.is_refusal
                      ? "Insufficient evidence"
                      : "Grounded answer"}
                  </span>
                </div>

                <div className="rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-card-strong)] p-5">
                  <p className="whitespace-pre-wrap text-sm leading-7 text-[var(--aq-text-soft)]">
                    {result.answer}
                  </p>

                  {result.citations.length > 0 && (
                    <div className="mt-5 flex flex-wrap gap-2">
                      {result.citations.map(
                        (citation) => (
                          <button
                            key={
                              citation.source_id
                            }
                            type="button"
                            onClick={() =>
                              setSelectedCitationId(
                                citation.source_id,
                              )
                            }
                            className={[
                              "h-8 rounded-lg border px-3 text-xs font-semibold transition",
                              selectedCitation?.source_id ===
                              citation.source_id
                                ? "border-[var(--aq-blue)] bg-[var(--aq-blue)] text-white"
                                : "border-[var(--aq-blue)] bg-[var(--aq-blue-soft)] text-[var(--aq-text)]",
                            ].join(" ")}
                          >
                            {
                              citation.source_id
                            }
                          </button>
                        ),
                      )}
                    </div>
                  )}

                  <div className="mt-5 flex items-center justify-between border-t border-[var(--aq-border)] pt-4">
                    <div className="text-[10px] text-[var(--aq-muted)]">
                      {
                        result.provider_name
                      }{" "}
                      • {result.model_name}
                    </div>

                    <button
                      type="button"
                      onClick={() => {
                        void copyAnswer();
                      }}
                      className="flex h-8 items-center gap-2 rounded-lg border border-[var(--aq-border)] bg-[var(--aq-control)] px-3 text-[10px] font-semibold"
                    >
                      <Copy size={12} />
                      Copy
                    </button>
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap gap-3 text-[9px] text-[var(--aq-muted)]">
                  <span>
                    Retrieved:{" "}
                    {
                      result.retrieved_count
                    }
                  </span>

                  <span>
                    Citations:{" "}
                    {
                      result.citation_count
                    }
                  </span>

                  <span>
                    Evidence tokens:{" "}
                    {
                      result.usage
                        .evidence_tokens
                    }
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Composer */}
        <form
          onSubmit={handleSubmit}
          className="m-5 rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-card-strong)] p-4"
        >
          <textarea
            rows={2}
            value={question}
            disabled={loading}
            onChange={(event) =>
              setQuestion(
                event.target.value,
              )
            }
            onKeyDown={(event) => {
              if (
                event.key === "Enter" &&
                !event.shiftKey
              ) {
                event.preventDefault();

                event.currentTarget
                  .form
                  ?.requestSubmit();
              }
            }}
            placeholder="Ask anything about your documents..."
            className="w-full resize-none bg-transparent text-sm text-[var(--aq-text)] outline-none placeholder:text-[var(--aq-muted)] disabled:opacity-60"
          />

          <div className="mt-3 flex items-center">
            <button
              type="button"
              disabled
              title="Attachment support coming later"
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--aq-border)] bg-[var(--aq-control)] opacity-50"
            >
              <Paperclip size={16} />
            </button>

            <div className="ml-auto flex items-center gap-3">
              <button
                type="button"
                className="flex h-10 items-center gap-2 rounded-full border border-[var(--aq-blue)] bg-[var(--aq-card)] px-4 text-xs font-semibold"
              >
                <Sparkles size={14} />
                Upgrade
              </button>

              <button
                type="button"
                disabled
                aria-label="Voice coming later"
                className="flex h-10 w-10 items-center justify-center rounded-full border border-[var(--aq-border)] bg-[var(--aq-card)] opacity-50"
              >
                <Mic size={18} />
              </button>

              <button
                type="submit"
                disabled={
                  loading ||
                  !question.trim()
                }
                className="flex h-10 items-center gap-2 rounded-xl bg-[var(--aq-blue)] px-5 text-xs font-semibold text-white transition hover:bg-[var(--aq-blue-hover)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? (
                  <LoaderCircle
                    size={14}
                    className="animate-spin"
                  />
                ) : (
                  <Send size={14} />
                )}

                {loading
                  ? "Thinking"
                  : "Send"}
              </button>
            </div>
          </div>
        </form>
      </section>

      {/* Evidence */}
      <section className="aq-panel flex min-h-0 flex-col p-5">
        <div>
          <h2 className="font-semibold">
            Evidence & citations
          </h2>

          <p className="mt-1 text-[10px] text-[var(--aq-muted)]">
            Sources retrieved for the latest answer.
          </p>
        </div>

        {!selectedCitation ? (
          <div className="flex flex-1 items-center justify-center text-center">
            <div className="max-w-[220px]">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-card)] text-[var(--aq-blue)]">
                <FileSearch size={20} />
              </div>

              <h3 className="mt-4 text-sm font-semibold">
                No evidence yet
              </h3>

              <p className="mt-2 text-xs leading-5 text-[var(--aq-muted)]">
                Ask a question to retrieve
                supporting document evidence.
              </p>
            </div>
          </div>
        ) : (
          <div className="aq-scrollbar mt-5 min-h-0 flex-1 overflow-y-auto">
            <div className="space-y-3">
              {result?.citations.map(
                (citation) => (
                  <button
                    key={
                      citation.source_id
                    }
                    type="button"
                    onClick={() =>
                      setSelectedCitationId(
                        citation.source_id,
                      )
                    }
                    className={[
                      "flex w-full items-start gap-3 rounded-xl border p-3 text-left transition",
                      selectedCitation.source_id ===
                      citation.source_id
                        ? "border-[var(--aq-blue)] bg-[var(--aq-blue-soft)]"
                        : "border-[var(--aq-border)] bg-[var(--aq-card)] hover:border-[var(--aq-border-hover)]",
                    ].join(" ")}
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--aq-blue)] text-[10px] font-bold text-white">
                      {
                        citation.source_id
                      }
                    </span>

                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-xs font-semibold">
                        {
                          citation.filename
                        }
                      </span>

                      <span className="mt-1 block text-[9px] text-[var(--aq-muted)]">
                        {
                          citation.source_label
                        }
                      </span>
                    </span>

                    <span className="shrink-0 text-[9px] font-semibold text-[var(--aq-success)]">
                      {formatSimilarity(
                        citation.similarity_score,
                      )}
                    </span>
                  </button>
                ),
              )}
            </div>

            <div className="mt-5 rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-xs font-semibold">
                    {
                      selectedCitation.filename
                    }
                  </p>

                  <p className="mt-1 text-[9px] text-[var(--aq-muted)]">
                    {
                      selectedCitation.source_label
                    }
                    {" • "}
                    {
                      selectedCitation.chunk_role
                    }
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => {
                    void copyEvidence();
                  }}
                  className="flex h-8 shrink-0 items-center gap-2 rounded-lg border border-[var(--aq-border)] bg-[var(--aq-control)] px-3 text-[9px] font-semibold"
                >
                  <Copy size={11} />
                  Copy
                </button>
              </div>

              {selectedCitation.section_path.length >
                0 && (
                <p className="mt-4 text-[9px] text-[var(--aq-cyan)]">
                  {selectedCitation.section_path.join(
                    " / ",
                  )}
                </p>
              )}

              <div className="mt-3 rounded-lg bg-[var(--aq-preview)] p-4 text-[var(--aq-preview-text)]">
                <p className="whitespace-pre-wrap text-xs leading-6">
                  {
                    selectedCitation.excerpt
                  }
                </p>
              </div>

              <div className="mt-4 flex flex-wrap gap-3 text-[9px] text-[var(--aq-muted)]">
                <span>
                  Similarity:{" "}
                  {formatSimilarity(
                    selectedCitation.similarity_score,
                  )}
                </span>

                {selectedCitation.start_page !==
                  null && (
                  <span>
                    Page{" "}
                    {
                      selectedCitation.start_page
                    }
                    {selectedCitation.end_page !==
                      null &&
                    selectedCitation.end_page !==
                      selectedCitation.start_page
                      ? `–${selectedCitation.end_page}`
                      : ""}
                  </span>
                )}

                {selectedCitation.was_truncated && (
                  <span>
                    Excerpt truncated
                  </span>
                )}
              </div>
            </div>
          </div>
        )}
      </section>
    </>
  );
}