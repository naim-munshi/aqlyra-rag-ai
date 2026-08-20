"use client";

import Image from "next/image";

import {
  File,
  FileCode2,
  FileSpreadsheet,
  FileText,
  Minus,
  Plus,
  Presentation,
  X,
} from "lucide-react";

import {
  useEffect,
  useState,
} from "react";

import type {
  DocumentResponse,
} from "@/types/document";


type AttachmentPreviewProps = {
  document: DocumentResponse;
  previewUrl?: string | null;
  removable?: boolean;
  onRemove?: () => void;
  compact?: boolean;
};


function formatFileSize(
  bytes: number,
) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  if (bytes < 1024 * 1024) {
    return `${(
      bytes / 1024
    ).toFixed(1)} KB`;
  }

  return `${(
    bytes /
    (1024 * 1024)
  ).toFixed(1)} MB`;
}


function fileLabel(
  document: DocumentResponse,
) {
  const extension =
    document.file_extension
      .replace(".", "")
      .toUpperCase();

  if (
    document.content_type.startsWith(
      "image/",
    )
  ) {
    return "Image";
  }

  switch (
    document.file_extension.toLowerCase()
  ) {
    case ".pdf":
      return "PDF";
    case ".docx":
      return "Document";
    case ".xlsx":
      return "Spreadsheet";
    case ".csv":
      return "Data";
    case ".pptx":
      return "Presentation";
    case ".md":
      return "Markdown";
    case ".txt":
      return "Text";
    default:
      return extension || "File";
  }
}


function FileIcon({
  document,
}: {
  document: DocumentResponse;
}) {
  const extension =
    document.file_extension.toLowerCase();

  if (
    extension === ".xlsx" ||
    extension === ".csv"
  ) {
    return (
      <FileSpreadsheet size={20} />
    );
  }

  if (extension === ".pptx") {
    return <Presentation size={20} />;
  }

  if (
    extension === ".md" ||
    extension === ".txt"
  ) {
    return <FileCode2 size={20} />;
  }

  if (
    extension === ".pdf" ||
    extension === ".docx"
  ) {
    return <FileText size={20} />;
  }

  return <File size={20} />;
}


export function AttachmentPreview({
  document,
  previewUrl = null,
  removable = false,
  onRemove,
  compact = false,
}: AttachmentPreviewProps) {
  const [viewerOpen, setViewerOpen] =
    useState(false);

  const [zoom, setZoom] =
    useState(1);

  const [
    fileViewerOpen,
    setFileViewerOpen,
  ] = useState(false);

  const isImage =
    document.content_type.startsWith(
      "image/",
    );


  useEffect(() => {
    if (!viewerOpen) {
      return;
    }

    function handleKeyDown(
      event: KeyboardEvent,
    ) {
      if (event.key === "Escape") {
        setZoom(1);
        setViewerOpen(false);
      }
    }

    window.addEventListener(
      "keydown",
      handleKeyDown,
    );

    return () => {
      window.removeEventListener(
        "keydown",
        handleKeyDown,
      );
    };
  }, [viewerOpen]);


  if (isImage && previewUrl) {
    return (
      <>
        <div
          className={[
            "group relative overflow-hidden rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-card)]",
            compact
              ? "w-[180px]"
              : "w-[240px]",
          ].join(" ")}
        >
          <button
            type="button"
            title="Open image"
            aria-label={`Open ${document.original_filename}`}
            onClick={() =>
              setViewerOpen(true)
            }
            className="block w-full cursor-zoom-in"
          >
            <Image
              src={previewUrl}
              alt={
                document.original_filename
              }
              width={480}
              height={320}
              unoptimized
              className={[
                "w-full object-cover transition duration-200 group-hover:opacity-90",
                compact
                  ? "h-[120px]"
                  : "max-h-[220px]",
              ].join(" ")}
            />
          </button>

          <div className="flex items-center gap-2 px-3 py-2">
            <div className="min-w-0 flex-1">
              <p className="truncate text-[10px] font-semibold text-[var(--aq-text)]">
                {
                  document
                    .original_filename
                }
              </p>

              <p className="mt-0.5 text-[9px] text-[var(--aq-muted)]">
                Image ·{" "}
                {formatFileSize(
                  document.file_size,
                )}
              </p>
            </div>
          </div>

          {removable && onRemove && (
            <button
              type="button"
              aria-label="Remove attachment"
              title="Remove"
              onClick={onRemove}
              className="absolute right-2 top-2 z-10 flex h-7 w-7 items-center justify-center rounded-full bg-black/70 text-white backdrop-blur transition hover:bg-black"
            >
              <X size={14} />
            </button>
          )}
        </div>

        {viewerOpen && (
          <div
            role="dialog"
            aria-modal="true"
            aria-label={
              document.original_filename
            }
            className="fixed inset-0 z-[200] flex flex-col bg-black/95 backdrop-blur-sm"
          >
            <div className="flex h-16 shrink-0 items-center gap-3 border-b border-white/10 px-4">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-white">
                  {
                    document
                      .original_filename
                  }
                </p>

                <p className="text-[10px] text-white/50">
                  {Math.round(
                    zoom * 100,
                  )}
                  %
                </p>
              </div>

              <button
                type="button"
                aria-label="Zoom out"
                title="Zoom out"
                disabled={zoom <= 0.5}
                onClick={() =>
                  setZoom(
                    (current) =>
                      Math.max(
                        0.5,
                        current - 0.25,
                      ),
                  )
                }
                className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/5 text-white transition hover:bg-white/10 disabled:opacity-30"
              >
                <Minus size={17} />
              </button>

              <button
                type="button"
                aria-label="Zoom in"
                title="Zoom in"
                disabled={zoom >= 4}
                onClick={() =>
                  setZoom(
                    (current) =>
                      Math.min(
                        4,
                        current + 0.25,
                      ),
                  )
                }
                className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/5 text-white transition hover:bg-white/10 disabled:opacity-30"
              >
                <Plus size={17} />
              </button>

              <button
                type="button"
                aria-label="Close image"
                title="Close"
                onClick={() => {
                  setZoom(1);
                  setViewerOpen(false);
                }}
                className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/5 text-white transition hover:bg-white/10"
              >
                <X size={18} />
              </button>
            </div>

            <div
              className="min-h-0 flex-1 overflow-auto p-6"
              onClick={() => {
                setZoom(1);
                setViewerOpen(false);
              }}
            >
              <div className="flex min-h-full min-w-full items-center justify-center">
                <div
                  onClick={(event) =>
                    event.stopPropagation()
                  }
                  style={{
                    transform:
                      `scale(${zoom})`,
                    transformOrigin:
                      "center center",
                  }}
                  className="transition-transform duration-150"
                >
                  <Image
                    src={previewUrl}
                    alt={
                      document
                        .original_filename
                    }
                    width={1600}
                    height={1200}
                    unoptimized
                    className="max-h-[78vh] w-auto max-w-[88vw] object-contain"
                  />
                </div>
              </div>
            </div>
          </div>
        )}
      </>
    );
  }


  const cardContent = (
    <>
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[var(--aq-control)] text-[var(--aq-blue)]">
        <FileIcon
          document={document}
        />
      </div>

      <div className="min-w-0 flex-1 pr-5">
        <p className="truncate text-[11px] font-semibold text-[var(--aq-text)]">
          {
            document.original_filename
          }
        </p>

        <p className="mt-1 text-[9px] text-[var(--aq-muted)]">
          {fileLabel(document)}
          {" · "}
          {formatFileSize(
            document.file_size,
          )}
        </p>
      </div>
    </>
  );


  return (
    <div
      className={[
        "relative",
        compact
          ? "max-w-[280px]"
          : "max-w-[360px]",
      ].join(" ")}
    >
      {previewUrl ? (
        <button
          type="button"
          onClick={() =>
            setFileViewerOpen(true)
          }
          title={`Open ${document.original_filename}`}
          aria-label={`Open ${document.original_filename}`}
          className="flex w-full items-center gap-3 rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] p-3 text-left transition hover:border-[var(--aq-blue)] hover:bg-[var(--aq-control)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--aq-blue)]"
        >
          {cardContent}
        </button>
      ) : (
        <div className="flex w-full items-center gap-3 rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] p-3">
          {cardContent}
        </div>
      )}

      {removable && onRemove && (
        <button
          type="button"
          aria-label="Remove attachment"
          title="Remove"
          onClick={onRemove}
          className="absolute right-2 top-2 z-10 text-[var(--aq-muted)] transition hover:text-[var(--aq-text)]"
        >
          <X size={13} />
        </button>
      )}

      {fileViewerOpen && previewUrl && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={
            document.original_filename
          }
          className="fixed inset-0 z-[200] flex flex-col bg-black/95 backdrop-blur-sm"
        >
          <div className="flex h-16 shrink-0 items-center gap-3 border-b border-white/10 px-4">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-white">
                {
                  document.original_filename
                }
              </p>

              <p className="text-[10px] text-white/50">
                {fileLabel(document)}
                {" · "}
                {formatFileSize(
                  document.file_size,
                )}
              </p>
            </div>

            <button
              type="button"
              aria-label="Close file"
              title="Close"
              onClick={() =>
                setFileViewerOpen(false)
              }
              className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/5 text-white transition hover:bg-white/10"
            >
              <X size={18} />
            </button>
          </div>

          <div className="min-h-0 flex-1 p-4">
            <iframe
              src={previewUrl}
              title={
                document.original_filename
              }
              className="h-full w-full rounded-xl border border-white/10 bg-white"
            />
          </div>
        </div>
      )}
    </div>
  );
}
