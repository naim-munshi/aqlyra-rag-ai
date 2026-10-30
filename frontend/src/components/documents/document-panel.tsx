"use client";

import {
  AlertCircle,
  CheckCircle2,
  FileText,
  Download,
  LoaderCircle,
  RefreshCw,
  Eye,
  FileSpreadsheet,
  Presentation,
  Upload,
} from "lucide-react";
import {
  ChangeEvent,
  useEffect,
  useRef,
  useState,
} from "react";

import { uploadViaPrivateCloud } from "@/lib/api/cloud-upload";

import type {
  DocumentListResponse,
  DocumentResponse,
  DocumentStatus,
} from "@/types/document";
import {
  OfficeDocumentViewer,
  isOfficeDocument,
} from "@/components/documents/office-document-viewer";

type ApiError = {
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

function getErrorMessage(
  data: ApiError | null,
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

function statusLabel(status: DocumentStatus) {
  switch (status) {
    case "uploaded":
      return "Uploaded";

    case "queued":
      return "Queued";

    case "processing":
      return "Processing";

    case "ready":
      return "Ready";

    case "failed":
      return "Failed";
  }
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  const kilobytes = bytes / 1024;

  if (kilobytes < 1024) {
    return `${kilobytes.toFixed(1)} KB`;
  }

  const megabytes = kilobytes / 1024;

  return `${megabytes.toFixed(1)} MB`;
}

export function DocumentPanel() {
  const fileInputRef =
    useRef<HTMLInputElement>(null);

  const [documents, setDocuments] = useState<
    DocumentResponse[]
  >([]);

  const [loading, setLoading] =
    useState(true);

  const [uploading, setUploading] =
    useState(false);

  const [recovering, setRecovering] = useState(false);
  const [recoveryNotice, setRecoveryNotice] = useState("");

  const [processingId, setProcessingId] =
    useState<string | null>(null);

  const [error, setError] =
    useState("");

  const [previewDocument, setPreviewDocument] =
    useState<DocumentResponse | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadInitialDocuments() {
      try {
        const response = await fetch(
          "/api/documents",
          {
            method: "GET",
            cache: "no-store",
          },
        );

        const data =
          (await response.json()) as
            | DocumentListResponse
            | ApiError;

        if (cancelled) {
          return;
        }

        if (!response.ok) {
          setError(
            getErrorMessage(
              data as ApiError,
              "Unable to load documents.",
            ),
          );

          return;
        }

        const documentList =
          data as DocumentListResponse;

        setDocuments(documentList.items);
      } catch {
        if (!cancelled) {
          setError(
            "Unable to connect to document service.",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadInitialDocuments();

    return () => {
      cancelled = true;
    };
  }, []);

  async function refreshDocuments() {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        "/api/documents",
        {
          method: "GET",
          cache: "no-store",
        },
      );

      const data =
        (await response.json()) as
          | DocumentListResponse
          | ApiError;

      if (!response.ok) {
        setError(
          getErrorMessage(
            data as ApiError,
            "Unable to load documents.",
          ),
        );

        return;
      }

      const documentList =
        data as DocumentListResponse;

      setDocuments(documentList.items);
    } catch {
      setError(
        "Unable to connect to document service.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function processDocument(
    documentId: string,
  ) {
    setProcessingId(documentId);
    setError("");

    try {
      const response = await fetch(
        `/api/documents/${encodeURIComponent(
          documentId,
        )}/process`,
        {
          method: "POST",
        },
      );

      const data =
        (await response.json()) as
          | DocumentResponse
          | ApiError;

      if (!response.ok) {
        setError(
          getErrorMessage(
            data as ApiError,
            "Document processing failed.",
          ),
        );

        await refreshDocuments();
        return;
      }

      const processedDocument =
        data as DocumentResponse;

      setDocuments((current) =>
        current.map((document) =>
          document.id === processedDocument.id
            ? processedDocument
            : document,
        ),
      );
    } catch {
      setError(
        "Unable to connect to document processing service.",
      );
    } finally {
      setProcessingId(null);
    }
  }

  async function recoverPendingUploads() {
    if (recovering) return;
    setRecovering(true);
    setError("");
    setRecoveryNotice("");
    try {
      const response = await fetch("/api/documents/cloud/recover", {
        method: "POST", credentials: "same-origin", cache: "no-store",
      });
      if (!response.ok) {
        setError("Unable to recover pending uploads. Please retry later.");
        return;
      }
      const result = (await response.json()) as {
        recovered?: DocumentResponse[];
        attempted?: number;
        failed?: number;
      };
      const recoveredCount = result.recovered?.length ?? 0;
      setRecoveryNotice(
        recoveredCount > 0
          ? `Recovered ${recoveredCount} private file(s). They are ready to download.`
          : (result.failed ?? 0) > 0
            ? "Some pending files could not be verified. They were preserved for another retry."
            : "No recoverable uploads found."
      );
      await refreshDocuments();
      if ((result.failed ?? 0) > 0) {
        setError("Some files still need recovery. Existing cloud objects were preserved.");
      }
    } catch {
      setError("Upload recovery temporarily unavailable.");
    } finally {
      setRecovering(false);
    }
  }

  async function handleFileChange(
    event: ChangeEvent<HTMLInputElement>,
  ) {
    const file =
      event.target.files?.[0];

    event.target.value = "";

    if (!file) {
      return;
    }

    setUploading(true);
    setError("");

    try {
      let uploadedDocument: DocumentResponse;

      if (process.env.NEXT_PUBLIC_CLOUD_UPLOAD_ENABLED === "true") {
        // No File bytes ever cross the Next.js API in cloud mode.
        uploadedDocument = await uploadViaPrivateCloud(file);
      } else {
        // Preserve existing local/staging upload behavior unchanged.
        const formData = new FormData();
        formData.append("file", file);
        const response = await fetch("/api/documents/upload", {
          method: "POST", body: formData,
        });
        const data = (await response.json()) as DocumentResponse | ApiError;
        if (!response.ok) {
          setError(
            getErrorMessage(data as ApiError, "Document upload failed."),
          );
          return;
        }
        uploadedDocument = data as DocumentResponse;
      }

      setDocuments((current) => [
        uploadedDocument,
        ...current.filter(
          (document) =>
            document.id !==
            uploadedDocument.id,
        ),
      ]);

      // A successful cloud upload means bytes are durable, not that
      // a quota-limited embedding provider has indexed the document.
      if (process.env.NEXT_PUBLIC_CLOUD_UPLOAD_PROXY_ENABLED === "true") {
        setError(
          "File saved in private storage. AI indexing is currently unavailable; you can retry processing later."
        );
        return;
      }

      await processDocument(
        uploadedDocument.id,
      );
    } catch (uploadError) {
      setError(
        uploadError instanceof Error
          ? uploadError.message
          : "Unable to connect to document upload service.",
      );
    } finally {
      setUploading(false);
    }
  }

  return (
    <section className="aq-panel flex min-h-0 flex-col p-4">
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.xlsx,.pptx,.txt,.md,.csv,.png,.jpg,.jpeg,.webp"
        className="hidden"
        onChange={handleFileChange}
      />

      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-semibold">
            Documents
          </h2>

          <p className="mt-1 text-[10px] text-[var(--aq-muted)]">
            {documents.length} document
            {documents.length === 1
              ? ""
              : "s"}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {process.env.NEXT_PUBLIC_CLOUD_UPLOAD_PROXY_ENABLED === "true" && (
            <button
              type="button"
              disabled={recovering || uploading}
              onClick={() => void recoverPendingUploads()}
              aria-label="Recover unfinished private file uploads"
              className="flex h-8 items-center gap-1 rounded-lg border border-[var(--aq-border)] px-2 text-[10px] font-semibold text-[var(--aq-muted)] hover:text-[var(--aq-text)] disabled:opacity-50"
            >
              <RefreshCw size={12} className={recovering ? "animate-spin" : ""} />
              {recovering ? "Recovering..." : "Recover uploads"}
            </button>
          )}

          <button
            type="button"
            aria-label="Refresh documents"
            disabled={loading}
            onClick={() => {
              void refreshDocuments();
            }}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--aq-border)] bg-[var(--aq-card)] text-[var(--aq-muted)] transition hover:text-[var(--aq-text)] disabled:opacity-50"
          >
            <RefreshCw
              size={14}
              className={
                loading
                  ? "animate-spin"
                  : ""
              }
            />
          </button>

          <button
            type="button"
            disabled={uploading}
            onClick={() =>
              fileInputRef.current?.click()
            }
            className="flex h-8 items-center gap-2 rounded-lg bg-[var(--aq-blue)] px-3 text-xs font-semibold text-white transition hover:bg-[var(--aq-blue-hover)] disabled:opacity-60"
          >
            {uploading ? (
              <LoaderCircle
                size={14}
                className="animate-spin"
              />
            ) : (
              <Upload size={14} />
            )}

            {uploading
              ? "Uploading"
              : "Upload"}
          </button>
        </div>
      </div>

      {recoveryNotice && (
        <p role="status" className="mt-3 text-xs text-[var(--aq-muted)]">
          {recoveryNotice}
        </p>
      )}

      {error && (
        <div className="mt-4 flex gap-2 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-xs leading-5 text-red-400">
          <AlertCircle
            size={15}
            className="mt-0.5 shrink-0"
          />

          <span>
            {error}
          </span>
        </div>
      )}

      <div className="aq-scrollbar mt-5 min-h-0 flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex h-full min-h-[220px] flex-col items-center justify-center text-center">
            <LoaderCircle
              size={24}
              className="animate-spin text-[var(--aq-blue)]"
            />

            <p className="mt-3 text-xs text-[var(--aq-muted)]">
              Loading documents...
            </p>
          </div>
        ) : documents.length === 0 ? (
          <div className="flex h-full min-h-[260px] flex-col items-center justify-center px-4 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-card)] text-[var(--aq-blue)]">
              <FileText size={21} />
            </div>

            <h3 className="mt-4 text-sm font-semibold">
              No documents yet
            </h3>

            <p className="mt-2 max-w-[210px] text-xs leading-5 text-[var(--aq-muted)]">
              Upload your first document
              to create a searchable
              knowledge source.
            </p>

            <button
              type="button"
              onClick={() =>
                fileInputRef.current?.click()
              }
              className="mt-5 flex h-9 items-center gap-2 rounded-xl bg-[var(--aq-blue)] px-4 text-xs font-semibold text-white"
            >
              <Upload size={14} />
              Upload document
            </button>

            <p className="mt-3 text-center text-[10px] leading-4 text-[var(--aq-muted)]">
              Word (.docx), Excel (.xlsx), PowerPoint (.pptx),
              PDF, TXT, Markdown, CSV and images.
              Older .doc/.xls/.ppt files should be converted to modern Office formats.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {documents.map(
              (document) => {
                const isProcessing =
                  processingId ===
                  document.id;

                return (
                  <article
                    key={document.id}
                    className="rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] p-3"
                  >
                    <div className="flex items-start gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--aq-blue-soft)] text-[var(--aq-blue)]">
                        {document.file_extension === ".xlsx"
                          ? <FileSpreadsheet size={16} />
                          : document.file_extension === ".pptx"
                            ? <Presentation size={16} />
                            : <FileText size={16} />}
                      </div>

                      <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-semibold text-[var(--aq-text)]">
                          {
                            document.original_filename
                          }
                        </p>

                        <div className="mt-1 flex flex-wrap items-center gap-2 text-[9px] text-[var(--aq-muted)]">
                          <span>
                            {formatFileSize(
                              document.file_size,
                            )}
                          </span>

                          {document.word_count !==
                            null && (
                            <>
                              <span>
                                •
                              </span>

                              <span>
                                {document.word_count.toLocaleString()}{" "}
                                words
                              </span>
                            </>
                          )}
                        </div>
                      </div>

                      <StatusBadge
                        status={
                          document.status
                        }
                        processing={
                          isProcessing
                        }
                      />
                    </div>

                    {document.error_message && (
                      <p className="mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-[10px] leading-4 text-red-400">
                        {
                          document.error_message
                        }
                      </p>
                    )}

                    {["uploaded", "ready", "failed"].includes(document.status) && (
                      <a
                        href={`/api/documents/${encodeURIComponent(document.id)}/content`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-3 inline-flex h-8 items-center gap-2 rounded-lg border border-[var(--aq-border)] bg-[var(--aq-control)] px-3 text-[10px] font-semibold hover:border-[var(--aq-blue)]"
                      >
                        <Download size={13} aria-hidden="true" />
                        Download original
                      </a>
                    )}

                    {document.status === "ready" &&
                      isOfficeDocument(document.file_extension) && (
                      <button
                        type="button"
                        onClick={() => setPreviewDocument(document)}
                        className="mt-3 flex h-8 items-center gap-2 rounded-lg border border-[var(--aq-border)] bg-[var(--aq-control)] px-3 text-[10px] font-semibold hover:border-[var(--aq-blue)]"
                      >
                        <Eye size={13} />
                        Preview extracted content
                      </button>
                    )}

                    {document.status ===
                      "uploaded" && (
                      <button
                        type="button"
                        disabled={
                          isProcessing
                        }
                        onClick={() => {
                          void processDocument(
                            document.id,
                          );
                        }}
                        className="mt-3 flex h-8 items-center gap-2 rounded-lg border border-[var(--aq-blue)] bg-[var(--aq-blue-soft)] px-3 text-[10px] font-semibold disabled:opacity-60"
                      >
                        {isProcessing ? (
                          <LoaderCircle
                            size={12}
                            className="animate-spin"
                          />
                        ) : (
                          <CheckCircle2
                            size={12}
                          />
                        )}

                        {isProcessing
                          ? "Processing..."
                          : "Process document"}
                      </button>
                    )}
                  </article>
                );
              },
            )}
          </div>
        )}
      </div>
      {previewDocument && (
        <OfficeDocumentViewer
          document={previewDocument}
          onClose={() => setPreviewDocument(null)}
        />
      )}
    </section>
  );
}

type StatusBadgeProps = {
  status: DocumentStatus;
  processing: boolean;
};

function StatusBadge({
  status,
  processing,
}: StatusBadgeProps) {
  if (
    processing ||
    status === "queued" ||
    status === "processing"
  ) {
    return (
      <span className="flex shrink-0 items-center gap-1.5 rounded-lg bg-[var(--aq-blue-soft)] px-2 py-1 text-[9px] font-semibold text-[var(--aq-blue)]">
        <LoaderCircle
          size={10}
          className="animate-spin"
        />

        Processing
      </span>
    );
  }

  if (status === "ready") {
    return (
      <span className="shrink-0 rounded-lg bg-emerald-500/10 px-2 py-1 text-[9px] font-semibold text-[var(--aq-success)]">
        Ready
      </span>
    );
  }

  if (status === "failed") {
    return (
      <span className="shrink-0 rounded-lg bg-red-500/10 px-2 py-1 text-[9px] font-semibold text-red-400">
        Failed
      </span>
    );
  }

  return (
    <span className="shrink-0 rounded-lg bg-[var(--aq-control)] px-2 py-1 text-[9px] font-semibold text-[var(--aq-muted)]">
      {statusLabel(status)}
    </span>
  );
}