"use client";

import {
  AlertCircle,
  Copy,
  FileText,
  LoaderCircle,
  Mic,
  PanelLeft,
  Paperclip,
  Send,
  Sparkles,
  X,
} from "lucide-react";
import {
  ChangeEvent,
  FormEvent,
  useEffect,
  useRef,
  useState,
} from "react";

import { DocumentPanel } from "@/components/documents/document-panel";
import type {
  DocumentListResponse,
  DocumentResponse,
} from "@/types/document";
import type {
  RAGAnswerResponse,
  RAGCitationResponse,
  RAGErrorResponse,
} from "@/types/rag";

type DocumentApiError = {
  detail?:
    | string
    | {
        message?: string;
        document_id?: string;
      }
    | Array<{
        msg?: string;
      }>;
};

type UploadState =
  | "idle"
  | "uploading"
  | "processing";

type ChatTurn = {
  id: string;
  question: string;
  loading: boolean;
  result: RAGAnswerResponse | null;
  error: string;
};

function getRagErrorMessage(
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

function getDocumentErrorMessage(
  data: DocumentApiError | null,
  fallback: string,
) {
  if (!data) {
    return fallback;
  }

  if (typeof data.detail === "string") {
    return data.detail;
  }

  if (
    data.detail &&
    !Array.isArray(data.detail) &&
    typeof data.detail === "object"
  ) {
    return data.detail.message ?? fallback;
  }

  if (Array.isArray(data.detail)) {
    return data.detail[0]?.msg ?? fallback;
  }

  return fallback;
}

function getDuplicateDocumentId(
  data: DocumentApiError,
) {
  if (
    data.detail &&
    !Array.isArray(data.detail) &&
    typeof data.detail === "object"
  ) {
    return data.detail.document_id ?? null;
  }

  return null;
}

function formatSimilarity(
  score: number,
) {
  return score.toFixed(3);
}

export function RAGWorkspace() {
  const fileInputRef =
    useRef<HTMLInputElement>(null);

  const chatEndRef =
    useRef<HTMLDivElement>(null);

  const abortRef =
    useRef<AbortController | null>(null);

  const [question, setQuestion] =
    useState("");

  const [turns, setTurns] =
    useState<ChatTurn[]>([]);

  const [
    attachedDocument,
    setAttachedDocument,
  ] = useState<DocumentResponse | null>(null);

  const [
    uploadState,
    setUploadState,
  ] = useState<UploadState>("idle");

  const [
    attachmentError,
    setAttachmentError,
  ] = useState("");

  const [
    documentDrawerOpen,
    setDocumentDrawerOpen,
  ] = useState(false);

  const [
    evidenceDrawerOpen,
    setEvidenceDrawerOpen,
  ] = useState(false);

  const [
    selectedTurnId,
    setSelectedTurnId,
  ] = useState<string | null>(null);

  const [
    selectedCitationId,
    setSelectedCitationId,
  ] = useState<string | null>(null);

  const [
    documentsVersion,
    setDocumentsVersion,
  ] = useState(0);

  const ragLoading =
    turns.some(
      (turn) => turn.loading,
    );

  const hasConversation =
    turns.length > 0;

  const selectedTurn =
    turns.find(
      (turn) =>
        turn.id === selectedTurnId,
    ) ?? null;

  const selectedCitation:
    | RAGCitationResponse
    | null =
    selectedTurn?.result?.citations.find(
      (citation) =>
        citation.source_id ===
        selectedCitationId,
    ) ??
    selectedTurn?.result?.citations[0] ??
    null;

  useEffect(() => {
    function resetChat() {
      abortRef.current?.abort();

      setQuestion("");
      setTurns([]);
      setAttachedDocument(null);
      setAttachmentError("");
      setUploadState("idle");
      setDocumentDrawerOpen(false);
      setEvidenceDrawerOpen(false);
      setSelectedTurnId(null);
      setSelectedCitationId(null);
    }

    function openDocuments() {
      setEvidenceDrawerOpen(false);
      setDocumentDrawerOpen(true);
    }

    function focusChat() {
      setDocumentDrawerOpen(false);
      setEvidenceDrawerOpen(false);
    }

    window.addEventListener(
      "aqlyra:new-chat",
      resetChat,
    );

    window.addEventListener(
      "aqlyra:open-documents",
      openDocuments,
    );

    window.addEventListener(
      "aqlyra:focus-chat",
      focusChat,
    );

    return () => {
      window.removeEventListener(
        "aqlyra:new-chat",
        resetChat,
      );

      window.removeEventListener(
        "aqlyra:open-documents",
        openDocuments,
      );

      window.removeEventListener(
        "aqlyra:focus-chat",
        focusChat,
      );
    };
  }, []);

  useEffect(() => {
    if (!hasConversation) {
      return;
    }

    chatEndRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "end",
    });
  }, [
    hasConversation,
    turns,
  ]);

  async function findExistingDocument(
    documentId: string,
  ) {
    const response = await fetch(
      "/api/documents",
      {
        cache: "no-store",
      },
    );

    if (!response.ok) {
      return null;
    }

    const data =
      (await response.json()) as
        DocumentListResponse;

    return (
      data.items.find(
        (document) =>
          document.id === documentId,
      ) ?? null
    );
  }

  async function ensureDocumentReady(
    document: DocumentResponse,
  ) {
    if (document.status === "ready") {
      return document;
    }

    if (document.status !== "uploaded") {
      throw new Error(
        `Document is currently ${document.status}.`,
      );
    }

    setUploadState("processing");

    const response = await fetch(
      `/api/documents/${encodeURIComponent(
        document.id,
      )}/process`,
      {
        method: "POST",
      },
    );

    const data =
      (await response.json()) as
        | DocumentResponse
        | DocumentApiError;

    if (!response.ok) {
      throw new Error(
        getDocumentErrorMessage(
          data as DocumentApiError,
          "Document processing failed.",
        ),
      );
    }

    return data as DocumentResponse;
  }

  async function handleAttachmentChange(
    event: ChangeEvent<HTMLInputElement>,
  ) {
    const file =
      event.target.files?.[0];

    event.target.value = "";

    if (!file) {
      return;
    }

    setAttachmentError("");
    setUploadState("uploading");

    try {
      const formData =
        new FormData();

      formData.append(
        "file",
        file,
      );

      const uploadResponse =
        await fetch(
          "/api/documents/upload",
          {
            method: "POST",
            body: formData,
          },
        );

      const uploadData =
        (await uploadResponse.json()) as
          | DocumentResponse
          | DocumentApiError;

      let document:
        DocumentResponse;

      if (!uploadResponse.ok) {
        const duplicateId =
          uploadResponse.status === 409
            ? getDuplicateDocumentId(
                uploadData as DocumentApiError,
              )
            : null;

        if (!duplicateId) {
          throw new Error(
            getDocumentErrorMessage(
              uploadData as DocumentApiError,
              "Document upload failed.",
            ),
          );
        }

        const existingDocument =
          await findExistingDocument(
            duplicateId,
          );

        if (!existingDocument) {
          throw new Error(
            "Unable to load the existing document.",
          );
        }

        document =
          existingDocument;
      } else {
        document =
          uploadData as DocumentResponse;
      }

      const readyDocument =
        await ensureDocumentReady(
          document,
        );

      setAttachedDocument(
        readyDocument,
      );

      setDocumentsVersion(
        (current) => current + 1,
      );
    } catch (uploadError) {
      setAttachmentError(
        uploadError instanceof Error
          ? uploadError.message
          : "Unable to attach document.",
      );
    } finally {
      setUploadState("idle");
    }
  }

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    const cleanedQuestion =
      question.trim();

    const effectiveQuestion =
      cleanedQuestion ||
      (attachedDocument
        ? "Summarize this document clearly and explain the key points."
        : "");

    const displayQuestion =
      cleanedQuestion ||
      (attachedDocument
        ? `Summarize ${attachedDocument.original_filename}`
        : "");

    if (
      !effectiveQuestion ||
      ragLoading ||
      uploadState !== "idle"
    ) {
      return;
    }

    const turnId =
      crypto.randomUUID();

    setQuestion("");

    setTurns((current) => [
      ...current,
      {
        id: turnId,
        question:
          displayQuestion,
        loading: true,
        result: null,
        error: "",
      },
    ]);

    setEvidenceDrawerOpen(false);

    const controller =
      new AbortController();

    abortRef.current =
      controller;

    try {
      const response =
        await fetch(
          "/api/rag/answer",
          {
            method: "POST",
            headers: {
              "Content-Type":
                "application/json",
            },
            body: JSON.stringify({
              question:
                effectiveQuestion,
              ...(attachedDocument
                ? {
                    document_ids: [
                      attachedDocument.id,
                    ],
                  }
                : {}),
            }),
            signal:
              controller.signal,
          },
        );

      const data =
        (await response.json()) as
          | RAGAnswerResponse
          | RAGErrorResponse;

      if (!response.ok) {
        const message =
          getRagErrorMessage(
            data as RAGErrorResponse,
          );

        setTurns((current) =>
          current.map((turn) =>
            turn.id === turnId
              ? {
                  ...turn,
                  loading: false,
                  error: message,
                }
              : turn,
          ),
        );

        return;
      }

      const result =
        data as RAGAnswerResponse;

      setTurns((current) =>
        current.map((turn) =>
          turn.id === turnId
            ? {
                ...turn,
                loading: false,
                result,
              }
            : turn,
        ),
      );
    } catch (requestError) {
      if (
        requestError instanceof
          DOMException &&
        requestError.name ===
          "AbortError"
      ) {
        return;
      }

      setTurns((current) =>
        current.map((turn) =>
          turn.id === turnId
            ? {
                ...turn,
                loading: false,
                error:
                  "Unable to connect to the RAG service.",
              }
            : turn,
        ),
      );
    } finally {
      if (
        abortRef.current ===
        controller
      ) {
        abortRef.current = null;
      }
    }
  }

  function openCitation(
    turnId: string,
    citationId: string,
  ) {
    setDocumentDrawerOpen(false);

    setSelectedTurnId(
      turnId,
    );

    setSelectedCitationId(
      citationId,
    );

    setEvidenceDrawerOpen(true);
  }

  async function copyAnswer(
    answer: string,
  ) {
    await navigator.clipboard.writeText(
      answer,
    );
  }

  async function copyEvidence() {
    if (!selectedCitation) {
      return;
    }

    await navigator.clipboard.writeText(
      selectedCitation.excerpt,
    );
  }

  function renderComposer(
    centered: boolean,
  ) {
    return (
      <form
        onSubmit={handleSubmit}
        className={[
          "w-full rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-card-strong)] p-4 shadow-xl",
          centered
            ? "max-w-[760px]"
            : "max-w-[900px]",
        ].join(" ")}
      >
        {attachedDocument && (
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <div className="flex max-w-full items-center gap-2 rounded-lg border border-[var(--aq-border)] bg-[var(--aq-card)] px-3 py-2">
              <FileText
                size={14}
                className="shrink-0 text-[var(--aq-blue)]"
              />

              <span className="max-w-[320px] truncate text-[11px] font-semibold">
                {
                  attachedDocument.original_filename
                }
              </span>

              <span className="text-[9px] font-semibold text-[var(--aq-success)]">
                Ready
              </span>

              <button
                type="button"
                onClick={() =>
                  setAttachedDocument(
                    null,
                  )
                }
                aria-label="Remove attached document"
                className="text-[var(--aq-muted)] transition hover:text-[var(--aq-text)]"
              >
                <X size={13} />
              </button>
            </div>
          </div>
        )}

        {attachmentError && (
          <div className="mb-3 flex items-center gap-2 text-[10px] text-red-400">
            <AlertCircle
              size={13}
            />

            {attachmentError}
          </div>
        )}

        <textarea
          rows={2}
          value={question}
          disabled={ragLoading}
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
          placeholder="Ask Aqlyra about your documents..."
          className="w-full resize-none bg-transparent text-sm leading-6 text-[var(--aq-text)] outline-none placeholder:text-[var(--aq-muted)]"
        />

        <div className="mt-3 flex items-center gap-3">
          <button
            type="button"
            aria-label="Attach document"
            disabled={
              uploadState !== "idle"
            }
            onClick={() =>
              fileInputRef.current?.click()
            }
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-[var(--aq-border)] bg-[var(--aq-control)] text-[var(--aq-muted)] transition hover:text-[var(--aq-blue)] disabled:opacity-50"
          >
            {uploadState === "idle" ? (
              <Paperclip
                size={16}
              />
            ) : (
              <LoaderCircle
                size={16}
                className="animate-spin"
              />
            )}
          </button>

          {uploadState !==
            "idle" && (
            <span className="text-[10px] text-[var(--aq-muted)]">
              {uploadState ===
              "uploading"
                ? "Uploading..."
                : "Processing..."}
            </span>
          )}

          <div className="ml-auto flex items-center gap-2">
            <button
              type="button"
              className="flex h-10 items-center gap-2 rounded-full border border-[var(--aq-border)] bg-[var(--aq-card)] px-4 text-xs font-semibold text-[var(--aq-text)] transition hover:bg-[var(--aq-control)]"
            >
              <Sparkles
                size={14}
                className="text-[var(--aq-cyan)]"
              />

              Upgrade
            </button>

            <button
              type="button"
              disabled
              aria-label="Voice coming later"
              className="flex h-10 w-10 items-center justify-center rounded-full border border-[var(--aq-border)] bg-[var(--aq-card)] text-[var(--aq-muted)]"
            >
              <Mic size={18} />
            </button>

            <button
              type="submit"
              disabled={
                ragLoading ||
                uploadState !== "idle" ||
                !question.trim() &&
                !attachedDocument
              }
              className="flex h-10 items-center gap-2 rounded-xl bg-[var(--aq-blue)] px-5 text-xs font-semibold text-white transition hover:bg-[var(--aq-blue-hover)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {ragLoading ? (
                <LoaderCircle
                  size={14}
                  className="animate-spin"
                />
              ) : (
                <Send size={14} />
              )}

              Send
            </button>
          </div>
        </div>
      </form>
    );
  }

  return (
    <div className="relative flex h-full min-h-0 overflow-hidden">
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.xlsx,.pptx,.txt,.md,.csv"
        className="hidden"
        onChange={
          handleAttachmentChange
        }
      />

      <section
        className={[
          "aq-panel flex min-h-0 flex-1 flex-col overflow-hidden transition-[padding] duration-200",
          evidenceDrawerOpen
            ? "lg:pr-[400px]"
            : "",
        ].join(" ")}
      >
        <div className="flex h-14 shrink-0 items-center border-b border-[var(--aq-border)] px-4">
          <button
            type="button"
            onClick={() => {
              setEvidenceDrawerOpen(
                false,
              );

              setDocumentDrawerOpen(
                true,
              );
            }}
            className="flex h-9 items-center gap-2 rounded-lg border border-[var(--aq-border)] bg-[var(--aq-card)] px-3 text-xs font-semibold"
          >
            <PanelLeft
              size={15}
            />

            Documents
          </button>

          <div className="ml-4 flex items-center gap-2">
            <Sparkles
              size={16}
              className="text-[var(--aq-cyan)]"
            />

            <span className="text-sm font-semibold">
              Aqlyra
            </span>
          </div>

          <span className="ml-auto rounded-full bg-[var(--aq-card)] px-3 py-1 text-[10px] font-semibold text-[var(--aq-success)]">
            Grounded RAG
          </span>
        </div>

        {!hasConversation ? (
          <div className="flex min-h-0 flex-1 items-center justify-center px-6 pb-12">
            <div className="flex w-full max-w-[760px] flex-col items-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-card)] text-[var(--aq-blue)]">
                <Sparkles
                  size={21}
                />
              </div>

              <h2 className="mt-5 text-xl font-semibold">
                Ask your knowledge base
              </h2>

              <p className="mt-2 max-w-[500px] text-center text-sm leading-6 text-[var(--aq-muted)]">
                Upload a document or ask a
                grounded question across your
                processed knowledge sources.
              </p>

              <div className="mt-7 w-full">
                {renderComposer(
                  true,
                )}
              </div>
            </div>
          </div>
        ) : (
          <>
            <div className="aq-scrollbar min-h-0 flex-1 overflow-y-auto px-6 py-8">
              <div className="mx-auto w-full max-w-[820px] space-y-10">
                {turns.map(
                  (turn) => (
                    <div
                      key={turn.id}
                    >
                      <div className="ml-auto max-w-[560px] rounded-2xl bg-[var(--aq-blue)] px-5 py-4 text-sm leading-6 text-white">
                        {
                          turn.question
                        }
                      </div>

                      <div className="mt-7">
                        <div className="mb-3 flex items-center gap-2">
                          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--aq-border)] bg-[var(--aq-card)] text-[10px] font-bold text-[var(--aq-cyan)]">
                            AQ
                          </div>

                          <span className="text-xs font-semibold">
                            Aqlyra
                          </span>
                        </div>

                        {turn.loading && (
                          <div className="flex items-center gap-3 rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-card-strong)] p-5">
                            <LoaderCircle
                              size={17}
                              className="animate-spin text-[var(--aq-blue)]"
                            />

                            <span className="text-xs text-[var(--aq-muted)]">
                              Retrieving evidence...
                            </span>
                          </div>
                        )}

                        {turn.error && (
                          <div className="flex gap-3 rounded-2xl border border-red-500/30 bg-red-500/10 p-5">
                            <AlertCircle
                              size={17}
                              className="text-red-400"
                            />

                            <p className="text-xs text-red-300">
                              {
                                turn.error
                              }
                            </p>
                          </div>
                        )}

                        {turn.result && (
                          <div className="rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-card-strong)] p-5">
                            <p className="whitespace-pre-wrap text-sm leading-7 text-[var(--aq-text-soft)]">
                              {
                                turn.result
                                  .answer
                              }
                            </p>

                            {turn.result.citations
                              .length >
                              0 && (
                              <div className="mt-5 flex flex-wrap gap-2">
                                {turn.result.citations.map(
                                  (
                                    citation,
                                  ) => (
                                    <button
                                      key={
                                        citation.source_id
                                      }
                                      type="button"
                                      onClick={() =>
                                        openCitation(
                                          turn.id,
                                          citation.source_id,
                                        )
                                      }
                                      className="rounded-lg border border-[var(--aq-blue)] bg-[var(--aq-blue-soft)] px-3 py-1.5 text-xs font-semibold"
                                    >
                                      {
                                        citation.source_id
                                      }{" "}
                                      ·{" "}
                                      {
                                        citation.filename
                                      }
                                    </button>
                                  ),
                                )}
                              </div>
                            )}

                            <div className="mt-5 flex items-center justify-between border-t border-[var(--aq-border)] pt-4">
                              <span className="text-[10px] text-[var(--aq-muted)]">
                                {
                                  turn.result.provider_name
                                }
                                {" · "}
                                {
                                  turn.result.model_name
                                }
                              </span>

                              <button
                                type="button"
                                onClick={() => {
                                  void copyAnswer(
                                    turn.result!
                                      .answer,
                                  );
                                }}
                                className="flex h-8 items-center gap-2 rounded-lg border border-[var(--aq-border)] bg-[var(--aq-control)] px-3 text-[10px] font-semibold"
                              >
                                <Copy
                                  size={12}
                                />

                                Copy
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  ),
                )}

                <div
                  ref={
                    chatEndRef
                  }
                />
              </div>
            </div>

            <div className="shrink-0 px-5 pb-5 pt-2">
              <div className="mx-auto max-w-[900px]">
                {renderComposer(
                  false,
                )}
              </div>
            </div>
          </>
        )}
      </section>

      {documentDrawerOpen && (
        <>
          <button
            type="button"
            aria-label="Close documents"
            onClick={() =>
              setDocumentDrawerOpen(
                false,
              )
            }
            className="absolute inset-0 z-20 bg-black/50"
          />

          <aside className="absolute inset-y-0 left-0 z-30 flex w-[360px] flex-col border-r border-[var(--aq-border)] bg-[var(--aq-bg-deep)] shadow-2xl">
            <div className="flex h-14 items-center justify-between border-b border-[var(--aq-border)] px-4">
              <div>
                <p className="text-sm font-semibold">
                  Documents
                </p>

                <p className="text-[9px] text-[var(--aq-muted)]">
                  Your knowledge sources
                </p>
              </div>

              <button
                type="button"
                onClick={() =>
                  setDocumentDrawerOpen(
                    false,
                  )
                }
                className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--aq-border)]"
              >
                <X size={15} />
              </button>
            </div>

            <div className="min-h-0 flex-1 p-3">
              <DocumentPanel
                key={
                  documentsVersion
                }
              />
            </div>
          </aside>
        </>
      )}

      {evidenceDrawerOpen &&
        selectedCitation &&
        selectedTurn?.result && (
          <aside className="absolute inset-y-0 right-0 z-30 flex w-[400px] flex-col border-l border-[var(--aq-border)] bg-[var(--aq-bg-deep)] shadow-2xl">
            <div className="flex h-14 items-center justify-between border-b border-[var(--aq-border)] px-4">
              <div>
                <p className="text-sm font-semibold">
                  Evidence
                </p>

                <p className="text-[9px] text-[var(--aq-muted)]">
                  Grounding sources
                </p>
              </div>

              <button
                type="button"
                onClick={() =>
                  setEvidenceDrawerOpen(
                    false,
                  )
                }
                className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--aq-border)]"
              >
                <X size={15} />
              </button>
            </div>

            <div className="aq-scrollbar min-h-0 flex-1 overflow-y-auto p-4">
              <div className="space-y-2">
                {selectedTurn.result.citations.map(
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
                        "flex w-full items-start gap-3 rounded-xl border p-3 text-left",
                        selectedCitation.source_id ===
                        citation.source_id
                          ? "border-[var(--aq-blue)] bg-[var(--aq-blue-soft)]"
                          : "border-[var(--aq-border)] bg-[var(--aq-card)]",
                      ].join(
                        " ",
                      )}
                    >
                      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--aq-blue)] text-[10px] font-bold text-white">
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

                      <span className="text-[9px] text-[var(--aq-success)]">
                        {formatSimilarity(
                          citation.similarity_score,
                        )}
                      </span>
                    </button>
                  ),
                )}
              </div>

              <div className="mt-4 rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] p-4">
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
                      {" · "}
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
                    className="flex h-8 items-center gap-2 rounded-lg border border-[var(--aq-border)] px-3 text-[9px]"
                  >
                    <Copy size={11} />
                    Copy
                  </button>
                </div>

                <div className="mt-3 rounded-lg bg-[var(--aq-preview)] p-4 text-[var(--aq-preview-text)]">
                  <p className="whitespace-pre-wrap text-xs leading-6">
                    {
                      selectedCitation.excerpt
                    }
                  </p>
                </div>
              </div>
            </div>
          </aside>
        )}
    </div>
  );
}