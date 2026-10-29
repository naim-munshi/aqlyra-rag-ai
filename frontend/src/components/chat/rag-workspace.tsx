"use client";

import {
  AlertCircle,
  Copy,
  Download,
  FilePlus2,
  LoaderCircle,
  PanelLeft,
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

import { AttachmentPreview } from "@/components/chat/attachment-preview";
import { ChatToolsMenu } from "@/components/chat/chat-tools-menu";
import { detectChatArtifactIntent, wantsChatArtifactList } from "@/lib/chat-artifact-intent";
import { MarkdownMessage } from "@/components/chat/markdown-message";
import { DocumentPanel } from "@/components/documents/document-panel";
import { VoiceCallButton } from "@/components/voice/voice-call-button";
import {
  buildConversationTitle,
} from "@/lib/conversation/title";

import type {
  ChatTurnResponse,
  ConversationMessageResponse,
  ConversationMode,
  ConversationResponse,
} from "@/types/conversation";
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

type ChatMode =
  ConversationMode;

type ChatArtifact = {
  id: string;
  filename: string;
  format: string;
};

type ChatTurn = {
  artifacts?: ChatArtifact[];
  id: string;
  mode: ChatMode;
  question: string;
  attachment?: {
    document: DocumentResponse;
    previewUrl: string | null;
  } | null;
  loading: boolean;
  streamedAnswer: string;
  result: RAGAnswerResponse | null;
  error: string;
};

type ParsedSseEvent = {
  event: string;
  data: unknown;
};

type NormalStreamStart = {
  conversation_id?: string;
  mode?: string;
};

type NormalStreamDelta = {
  text?: string;
};

type NormalStreamError = {
  status?: number;
  code?: string;
  detail?: string;
};

type OpenConversationDetail = {
  id?: string;
  title?: string;
  mode?: ConversationMode;
};

type DeletedConversationDetail = {
  id?: string;
};

type PersistedWorkspaceState = {
  mode: ChatMode;
  conversationId: string | null;
  draft: string;
};

type RAGWorkspaceProps = {
  userId: string;
};

const LEGACY_WORKSPACE_STORAGE_KEY =
  "aqlyra:active-workspace:v1";

function workspaceStorageKey(
  userId: string,
) {
  return `aqlyra:active-workspace:v2:${userId}`;
}

function parseSseFrame(
  frame: string,
): ParsedSseEvent | null {
  const lines =
    frame.split(/\r?\n/);

  let eventName = "";

  const dataLines: string[] = [];

  for (const line of lines) {
    if (
      line.startsWith("event: ")
    ) {
      eventName =
        line.slice(7).trim();

      continue;
    }

    if (
      line.startsWith("data: ")
    ) {
      dataLines.push(
        line.slice(6),
      );
    }
  }

  if (
    !eventName ||
    dataLines.length === 0
  ) {
    return null;
  }

  try {
    return {
      event: eventName,
      data: JSON.parse(
        dataLines.join("\n"),
      ),
    };
  } catch {
    return null;
  }
}


function normalResultFromTurn(
  question: string,
  turn: ChatTurnResponse,
): RAGAnswerResponse {
  const assistant =
    turn.assistant_message;

  const citations =
    assistant.citations ?? [];

  return {
    question,
    answer: assistant.content,
    is_refusal:
      assistant.is_refusal,
    provider_name:
      assistant.provider_name ??
      "unknown",
    model_name:
      assistant.model_name ??
      "unknown",
    response_id:
      assistant.response_id,
    citations,
    citation_count:
      citations.length,
    retrieved_count:
      citations.length,
    context_source_count:
      citations.length,
    skipped_evidence_count: 0,
    evidence_was_truncated: false,
    usage: {
      input_tokens:
        assistant.input_tokens,
      output_tokens:
        assistant.output_tokens,
      total_tokens:
        assistant.total_tokens,
      evidence_tokens:
        assistant.evidence_tokens ??
        0,
    },
  };
}


function persistedResultFromMessage(
  question: string,
  assistant: ConversationMessageResponse,
): RAGAnswerResponse {
  const citations =
    assistant.citations ?? [];

  return {
    question,
    answer: assistant.content,
    is_refusal:
      assistant.is_refusal,
    provider_name:
      assistant.provider_name ??
      "unknown",
    model_name:
      assistant.model_name ??
      "unknown",
    response_id:
      assistant.response_id,
    citations,
    citation_count:
      citations.length,
    retrieved_count:
      citations.length,
    context_source_count:
      citations.length,
    skipped_evidence_count: 0,
    evidence_was_truncated: false,
    usage: {
      input_tokens:
        assistant.input_tokens,
      output_tokens:
        assistant.output_tokens,
      total_tokens:
        assistant.total_tokens,
      evidence_tokens:
        assistant.evidence_tokens ??
        0,
    },
  };
}


function turnsFromPersistedMessages(
  messages: ConversationMessageResponse[],
): ChatTurn[] {
  const restored: ChatTurn[] = [];

  for (
    let index = 0;
    index < messages.length;
    index += 1
  ) {
    const userMessage =
      messages[index];

    const assistantMessage =
      messages[index + 1];

    if (
      userMessage?.role !== "user" ||
      assistantMessage?.role !==
        "assistant"
    ) {
      continue;
    }

    const persistedAttachment =
      userMessage.attachments?.[0];

    restored.push({
      id: assistantMessage.id,
      mode: userMessage.mode,
      question:
        userMessage.content,
      attachment:
        persistedAttachment
          ? {
              document:
                persistedAttachment.document,
              previewUrl:
                `/api/documents/${encodeURIComponent(
                  persistedAttachment
                    .document_id,
                )}/content`,
            }
          : null,
      loading: false,
      streamedAnswer:
        assistantMessage.content,
      result:
        persistedResultFromMessage(
          userMessage.content,
          assistantMessage,
        ),
      error: "",
    });

    index += 1;
  }

  return restored;
}


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

export function RAGWorkspace({
  userId,
}: RAGWorkspaceProps) {
  const storageKey =
    workspaceStorageKey(userId);

  const fileInputRef =
    useRef<HTMLInputElement>(null);

  const chatEndRef =
    useRef<HTMLDivElement>(null);

  const abortRef =
    useRef<AbortController | null>(null);

  const voiceConversationIdRef =
    useRef<string | null>(null);

  const [question, setQuestion] =
    useState("");
  const [webMode, setWebMode] =
    useState<"auto" | "off" | "on" | "deep">("auto");

  const [
    workspaceHydrated,
    setWorkspaceHydrated,
  ] = useState(false);

  const [
    copiedAnswerId,
    setCopiedAnswerId,
  ] = useState<string | null>(null);

  const [turns, setTurns] =
    useState<ChatTurn[]>([]);

  const [
    chatMode,
    setChatMode,
  ] = useState<ChatMode>(
    "normal",
  );

  const [
    normalConversationId,
    setNormalConversationId,
  ] = useState<string | null>(
    null,
  );

  const [
    knowledgeConversationId,
    setKnowledgeConversationId,
  ] = useState<string | null>(
    null,
  );

  const [
    attachedDocument,
    setAttachedDocument,
  ] = useState<DocumentResponse | null>(null);

  const [
    attachmentPreviewUrl,
    setAttachmentPreviewUrl,
  ] = useState<string | null>(null);

  const attachmentObjectUrlsRef =
    useRef<Set<string>>(
      new Set(),
    );

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

  function switchChatMode(
    nextMode: ChatMode,
  ) {
    if (
      nextMode === chatMode ||
      ragLoading
    ) {
      return;
    }

    abortRef.current?.abort();

    setChatMode(nextMode);

    window.dispatchEvent(
      new CustomEvent(
        "aqlyra:chat-mode-changed",
        {
          detail: {
            mode: nextMode,
          },
        },
      ),
    );

    setQuestion("");
    setTurns([]);

    setNormalConversationId(
      null,
    );

    setKnowledgeConversationId(
      null,
    );

    setAttachedDocument(null);
    setAttachmentError("");
    setUploadState("idle");

    setDocumentDrawerOpen(false);
    setEvidenceDrawerOpen(false);

    setSelectedTurnId(null);
    setSelectedCitationId(null);
  }


  useEffect(() => {
    function resetChat() {
      abortRef.current?.abort();

      setQuestion("");
      setTurns([]);
      setNormalConversationId(
        null,
      );

      setKnowledgeConversationId(
        null,
      );

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

    function handleConversationDeleted(
      event: Event,
    ) {
      const detail =
        (
          event as CustomEvent<
            DeletedConversationDetail
          >
        ).detail;

      if (
        !detail ||
        typeof detail.id !== "string"
      ) {
        return;
      }

      if (
        detail.id !==
          normalConversationId &&
        detail.id !==
          knowledgeConversationId
      ) {
        return;
      }

      resetChat();
    }

    window.addEventListener(
      "aqlyra:new-chat",
      resetChat,
    );

    window.addEventListener(
      "aqlyra:conversation-deleted",
      handleConversationDeleted,
    );

    window.addEventListener(
      "aqlyra:open-documents",
      openDocuments,
    );

    window.addEventListener(
      "aqlyra:focus-chat",
      focusChat,
    );

    // Sidebar controls on AI Files/other pages navigate here with an
    // explicit intent; the destination must process it after mounting.
    const pageUrl = new URL(window.location.href);
    const intent = pageUrl.searchParams.get("aqlyraIntent");
    if (intent === "documents") {
      openDocuments();
    } else if (intent === "new-chat") {
      resetChat();
    } else if (intent === "focus") {
      focusChat();
    }
    if (["documents", "new-chat", "focus"].includes(intent ?? "")) {
      pageUrl.searchParams.delete("aqlyraIntent");
      window.history.replaceState(
        window.history.state, "",
        pageUrl.pathname + pageUrl.search + pageUrl.hash,
      );
    }

    return () => {
      window.removeEventListener(
        "aqlyra:new-chat",
        resetChat,
      );

      window.removeEventListener(
        "aqlyra:conversation-deleted",
        handleConversationDeleted,
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
  }, [
    normalConversationId,
    knowledgeConversationId,
  ]);

  useEffect(() => {
    function openConversation(
      event: Event,
    ) {
      const detail =
        (
          event as CustomEvent<
            OpenConversationDetail
          >
        ).detail;

      if (
        !detail ||
        typeof detail.id !==
          "string" ||
        (
          detail.mode !== "normal" &&
          detail.mode !== "knowledge"
        )
      ) {
        return;
      }

      abortRef.current?.abort();

      const controller =
        new AbortController();

      abortRef.current =
        controller;

      void (async () => {
        try {
          const response =
            await fetch(
              `/api/conversations/${encodeURIComponent(
                detail.id!,
              )}/messages`,
              {
                cache: "no-store",
                signal:
                  controller.signal,
              },
            );

          const data =
            (await response.json()) as
              | ConversationMessageResponse[]
              | {
                  detail?: unknown;
                };

          if (
            !response.ok ||
            !Array.isArray(data)
          ) {
            if (response.status === 404) {
              try {
                window.localStorage.removeItem(
                  storageKey,
                );
              } catch {
                // Workspace persistence is best effort.
              }

              setQuestion("");
              setTurns([]);

              setNormalConversationId(
                null,
              );

              setKnowledgeConversationId(
                null,
              );
            }

            return;
          }

          setChatMode(
            detail.mode!,
          );

          setNormalConversationId(
            detail.mode === "normal"
              ? detail.id!
              : null,
          );

          setKnowledgeConversationId(
            detail.mode === "knowledge"
              ? detail.id!
              : null,
          );

          window.dispatchEvent(
            new CustomEvent(
              "aqlyra:chat-mode-changed",
              {
                detail: {
                  mode:
                    detail.mode,
                },
              },
            ),
          );

          setQuestion("");

          setTurns(
            turnsFromPersistedMessages(
              data,
            ),
          );

          setAttachedDocument(null);
          setAttachmentError("");
          setUploadState("idle");

          setDocumentDrawerOpen(
            false,
          );

          setEvidenceDrawerOpen(
            false,
          );

          setSelectedTurnId(null);
          setSelectedCitationId(null);
        } catch (error) {
          if (
            error instanceof
              DOMException &&
            error.name ===
              "AbortError"
          ) {
            return;
          }
        } finally {
          if (
            abortRef.current ===
            controller
          ) {
            abortRef.current =
              null;
          }
        }
      })();
    }

    window.addEventListener(
      "aqlyra:open-conversation",
      openConversation,
    );

    return () => {
      window.removeEventListener(
        "aqlyra:open-conversation",
        openConversation,
      );
    };
  }, [storageKey]);


  useEffect(() => {
    let restoredMode: ChatMode =
      "normal";

    let restoredConversationId:
      string | null = null;

    let restoredDraft = "";

    try {
      window.localStorage.removeItem(
        LEGACY_WORKSPACE_STORAGE_KEY,
      );

      const raw =
        window.localStorage.getItem(
          storageKey,
        );

      if (raw) {
        const parsed =
          JSON.parse(raw) as
            Partial<
              PersistedWorkspaceState
            >;

        if (
          parsed.mode === "normal" ||
          parsed.mode === "knowledge"
        ) {
          restoredMode =
            parsed.mode;
        }

        if (
          typeof
            parsed.conversationId ===
            "string" &&
          parsed.conversationId.trim()
        ) {
          restoredConversationId =
            parsed.conversationId.trim();
        }

        if (
          typeof parsed.draft ===
          "string"
        ) {
          restoredDraft =
            parsed.draft;
        }
      }
    } catch {
      window.localStorage.removeItem(
        storageKey,
      );
    }

    // A project created on a different page passes its new conversation
    // through a short-lived navigation intent. The message endpoint remains
    // owner-checked and is responsible for authorizing the requested ID.
    const navigationUrl = new URL(window.location.href);
    const requestedId = navigationUrl.searchParams.get("aqlyraConversationId");
    const requestedMode = navigationUrl.searchParams.get("aqlyraConversationMode");
    if (
      requestedId &&
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(requestedId) &&
      (requestedMode === "normal" || requestedMode === "knowledge")
    ) {
      restoredMode = requestedMode;
      restoredConversationId = requestedId;
      restoredDraft = "";
    }
    if (requestedId !== null || requestedMode !== null) {
      navigationUrl.searchParams.delete("aqlyraConversationId");
      navigationUrl.searchParams.delete("aqlyraConversationMode");
      window.history.replaceState(
        window.history.state,
        "",
        navigationUrl.pathname + navigationUrl.search + navigationUrl.hash,
      );
    }

    const restoreTimer =
      window.setTimeout(() => {
        setChatMode(restoredMode);
        setQuestion(restoredDraft);

        if (
          restoredMode === "normal"
        ) {
          setNormalConversationId(
            restoredConversationId,
          );

          setKnowledgeConversationId(
            null,
          );
        } else {
          setKnowledgeConversationId(
            restoredConversationId,
          );

          setNormalConversationId(
            null,
          );
        }

        window.dispatchEvent(
          new CustomEvent(
            "aqlyra:chat-mode-changed",
            {
              detail: {
                mode: restoredMode,
              },
            },
          ),
        );

        if (restoredConversationId) {
          window.dispatchEvent(
            new CustomEvent(
              "aqlyra:open-conversation",
              {
                detail: {
                  id:
                    restoredConversationId,
                  mode:
                    restoredMode,
                },
              },
            ),
          );
        }

        setWorkspaceHydrated(true);
      }, 0);

    return () => {
      window.clearTimeout(
        restoreTimer,
      );
    };
  }, [storageKey]);


  useEffect(() => {
    if (!workspaceHydrated) {
      return;
    }

    const conversationId =
      chatMode === "normal"
        ? normalConversationId
        : knowledgeConversationId;

    const state:
      PersistedWorkspaceState = {
        mode: chatMode,
        conversationId,
        draft: question,
      };

    try {
      window.localStorage.setItem(
        storageKey,
        JSON.stringify(state),
      );
    } catch {
      // Workspace persistence is best effort.
    }
  }, [
    workspaceHydrated,
    chatMode,
    normalConversationId,
    knowledgeConversationId,
    question,
    storageKey,
  ]);


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

    let localPreviewUrl:
      string | null = null;

    if (
      file.type.startsWith(
        "image/",
      )
    ) {
      localPreviewUrl =
        URL.createObjectURL(file);

      attachmentObjectUrlsRef
        .current
        .add(localPreviewUrl);
    }

    setAttachmentPreviewUrl(
      localPreviewUrl,
    );

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
            uploadResponse.status === 503
              ? "Secure file uploads are temporarily unavailable. You can still chat without a file."
              : getDocumentErrorMessage(
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

      // Private upload is durable, but RAG indexing is independently
      // gated by the embedding provider. Never claim an uploaded file
      // is already AI-ready when cloud beta is active.
      if (
        process.env.NEXT_PUBLIC_CLOUD_UPLOAD_PROXY_ENABLED === "true" &&
        document.status === "uploaded"
      ) {
        setAttachedDocument(null);
        setDocumentsVersion((current) => current + 1);
        setAttachmentError(
          "File saved in private storage. Open Documents to review it; AI indexing is not yet available."
        );
        return;
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
      setAttachmentPreviewUrl(
        null,
      );

      setAttachmentError(
        uploadError instanceof Error
          ? uploadError.message
          : "Unable to attach document.",
      );
    } finally {
      setUploadState("idle");
    }
  }

  async function refreshVoiceConversation(
    conversationId: string,
  ) {
    try {
      const response =
        await fetch(
          `/api/conversations/${encodeURIComponent(
            conversationId,
          )}/messages`,
          {
            method: "GET",
            cache: "no-store",
          },
        );

      const data =
        (await response.json()) as
          | ConversationMessageResponse[]
          | RAGErrorResponse;

      if (
        !response.ok ||
        !Array.isArray(data)
      ) {
        return;
      }

      setTurns(
        turnsFromPersistedMessages(
          data,
        ),
      );

      setQuestion("");

      window.dispatchEvent(
        new Event(
          "aqlyra:conversations-changed",
        ),
      );

      if (
        chatMode === "normal" &&
        attachedDocument
      ) {
        setAttachedDocument(
          null,
        );
      }
    } catch {
      // Live transcript remains visible in the
      // voice panel if history refresh fails.
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
        ? chatMode === "normal"
          ? (
              "Briefly explain this upload, "
              + "highlight the most useful "
              + "details you can determine, "
              + "then ask one specific "
              + "follow-up question that "
              + "makes sense for this content."
            )
          : (
              "Summarize this document "
              + "clearly and explain the "
              + "key points."
            )
        : "");

    const displayQuestion =
      cleanedQuestion;

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
        mode: chatMode,
        question:
          displayQuestion,
        attachment:
          attachedDocument
            ? {
                document:
                  attachedDocument,
                previewUrl:
                  attachmentPreviewUrl,
              }
            : null,
        loading: true,
        streamedAnswer: "",
        result: null,
        error: "",
      },
    ]);

    setAttachedDocument(null);
    setAttachmentPreviewUrl(null);

    setEvidenceDrawerOpen(false);

    const controller =
      new AbortController();

    abortRef.current =
      controller;

    try {
      // Explicit file requests are executed through the existing authenticated
      // artifact API. Document evidence requires affirmative user consent;
      // ordinary questions continue through RAG/conversation unchanged.
      const fileIntent = detectChatArtifactIntent(effectiveQuestion);
      if (fileIntent) {
        const documentIds = attachedDocument ? [attachedDocument.id] : [];
        const allowSources = documentIds.length === 0 ||
          window.confirm(
            "Share excerpts from the selected private document with the configured AI provider to create the requested file?",
          );
        if (!allowSources) {
          setTurns(current => current.filter(turn => turn.id !== turnId));
          setQuestion(effectiveQuestion);
          setAttachedDocument(attachedDocument);
          setAttachmentPreviewUrl(attachmentPreviewUrl);
          return;
        }
        const generated: ChatArtifact[] = [];
        try {
          for (const format of fileIntent.formats) {
            const response = await fetch("/api/artifacts/generate", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                title: fileIntent.title,
                prompt: fileIntent.prompt,
                format,
                document_ids: documentIds,
                confirm_share_documents: documentIds.length > 0 && allowSources,
              }),
              signal: controller.signal,
            });
            const data = await response.json() as {
              id?: string; filename?: string; format?: string; detail?: string;
            };
            if (!response.ok || typeof data.id !== "string" ||
                typeof data.filename !== "string") {
              throw new Error(
                typeof data.detail === "string" ? data.detail : "Unable to generate the requested file.",
              );
            }
            generated.push({ id: data.id, filename: data.filename, format });
          }
          setTurns(current => current.map(turn => turn.id === turnId
            ? {
                ...turn, loading: false, artifacts: generated,
                streamedAnswer: generated.length === 1
                  ? "File created. Download it below."
                  : "Files created. Download them below.",
              }
            : turn));
        } catch (fileError) {
          setTurns(current => current.map(turn => turn.id === turnId
            ? {
                ...turn, loading: false, artifacts: generated,
                error: fileError instanceof Error ? fileError.message : "File generation failed.",
                streamedAnswer: generated.length > 0
                  ? "These files were created before an error occurred:"
                  : "",
              }
            : turn));
        }
        return;
      }
      if (wantsChatArtifactList(effectiveQuestion)) {
        const response = await fetch("/api/artifacts", {
          cache: "no-store", signal: controller.signal,
        });
        const data = await response.json() as {
          items?: ChatArtifact[]; detail?: string;
        };
        if (!response.ok) throw new Error(
          typeof data.detail === "string" ? data.detail : "Cannot load files.",
        );
        const artifacts = Array.isArray(data.items) ? data.items : [];
        setTurns(current => current.map(turn => turn.id === turnId
          ? {
              ...turn, loading: false, artifacts,
              streamedAnswer: artifacts.length
                ? "Your generated files (private to your account):"
                : "You have no generated files yet. Ask me to create a Word, PDF, Excel, PowerPoint or Markdown file.",
            }
          : turn));
        return;
      }
      if (chatMode === "normal") {
        const response =
          await fetch(
            "/api/chat/normal/stream",
            {
              method: "POST",
              headers: {
                "Content-Type":
                  "application/json",
              },
              body: JSON.stringify({
                content:
                  effectiveQuestion,
                web_mode: chatMode === "normal" && !attachedDocument ? webMode : "off",
                display_content:
                  displayQuestion,
                ...(normalConversationId
                  ? {
                      conversation_id:
                        normalConversationId,
                    }
                  : {}),
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

        if (!response.ok) {
          let data:
            | RAGErrorResponse
            | null = null;

          try {
            data =
              (await response.json()) as
                RAGErrorResponse;
          } catch {
            data = null;
          }

          throw new Error(
            getRagErrorMessage(data),
          );
        }

        if (!response.body) {
          throw new Error(
            "Conversation stream is unavailable.",
          );
        }

        const reader =
          response.body.getReader();

        const decoder =
          new TextDecoder();

        let buffer = "";
        let completed = false;

        function handleFrame(
          frame: string,
        ) {
          const parsed =
            parseSseFrame(frame);

          if (!parsed) {
            return;
          }

          if (
            parsed.event === "start"
          ) {
            const data =
              parsed.data as
                NormalStreamStart;

            if (
              typeof data
                .conversation_id ===
                "string"
            ) {
              setNormalConversationId(
                data.conversation_id,
              );
            }

            return;
          }

          if (
            parsed.event === "delta"
          ) {
            const data =
              parsed.data as
                NormalStreamDelta;

            if (
              typeof data.text !==
                "string" ||
              !data.text
            ) {
              return;
            }

            setTurns((current) =>
              current.map((turn) =>
                turn.id === turnId
                  ? {
                      ...turn,
                      streamedAnswer:
                        turn.streamedAnswer +
                        data.text,
                    }
                  : turn,
              ),
            );

            return;
          }

          if (
            parsed.event === "error"
          ) {
            const data =
              parsed.data as
                NormalStreamError;

            throw new Error(
              typeof data.detail ===
                "string"
                ? data.detail
                : "Conversation streaming failed.",
            );
          }

          if (
            parsed.event ===
            "complete"
          ) {
            const data =
              parsed.data as
                ChatTurnResponse;

            if (
              typeof data
                .conversation_id ===
                "string"
            ) {
              setNormalConversationId(
                data.conversation_id,
              );
            }

            const result =
              normalResultFromTurn(
                effectiveQuestion,
                data,
              );

            setTurns((current) =>
              current.map((turn) =>
                turn.id === turnId
                  ? {
                      ...turn,
                      loading: false,
                      streamedAnswer:
                        result.answer,
                      result,
                      error: "",
                    }
                  : turn,
              ),
            );

            window.dispatchEvent(
              new Event(
                "aqlyra:conversations-changed",
              ),
            );

            if (attachedDocument) {
              setAttachedDocument(
                null,
              );
            }

            completed = true;
          }
        }

        while (true) {
          const {
            value,
            done,
          } = await reader.read();

          if (value) {
            buffer +=
              decoder.decode(
                value,
                {
                  stream: !done,
                },
              );
          }

          if (done) {
            buffer +=
              decoder.decode();
          }

          let boundary =
            buffer.indexOf(
              "\n\n",
            );

          while (boundary >= 0) {
            const frame =
              buffer.slice(
                0,
                boundary,
              );

            buffer =
              buffer.slice(
                boundary + 2,
              );

            if (frame.trim()) {
              handleFrame(frame);
            }

            boundary =
              buffer.indexOf(
                "\n\n",
              );
          }

          if (done) {
            break;
          }
        }

        if (buffer.trim()) {
          handleFrame(buffer);
        }

        if (!completed) {
          throw new Error(
            "Conversation stream ended before completion.",
          );
        }

        return;
      }

      let conversationId =
        knowledgeConversationId;

      if (!conversationId) {
        const title =
          attachedDocument
            ? attachedDocument
                .original_filename
                .slice(0, 200)
            : buildConversationTitle(
                effectiveQuestion,
              );

        const createResponse =
          await fetch(
            "/api/conversations",
            {
              method: "POST",
              headers: {
                "Content-Type":
                  "application/json",
              },
              body: JSON.stringify({
                title,
                mode: "knowledge",
              }),
              signal:
                controller.signal,
            },
          );

        const createData =
          (await createResponse.json()) as
            | ConversationResponse
            | RAGErrorResponse;

        if (!createResponse.ok) {
          throw new Error(
            getRagErrorMessage(
              createData as
                RAGErrorResponse,
            ),
          );
        }

        if (
          !("id" in createData) ||
          typeof createData.id !==
            "string"
        ) {
          throw new Error(
            "Unable to create knowledge conversation.",
          );
        }

        conversationId =
          createData.id;

        setKnowledgeConversationId(
          conversationId,
        );
      }

      const response =
        await fetch(
          `/api/conversations/${encodeURIComponent(
            conversationId,
          )}/messages`,
          {
            method: "POST",
            headers: {
              "Content-Type":
                "application/json",
            },
            body: JSON.stringify({
              content:
                effectiveQuestion,
              display_content:
                displayQuestion,
              document_ids:
                attachedDocument
                  ? [
                      attachedDocument.id,
                    ]
                  : [],
            }),
            signal:
              controller.signal,
          },
        );

      const data =
        (await response.json()) as
          | ChatTurnResponse
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

      const chatTurn =
        data as ChatTurnResponse;

      const result =
        persistedResultFromMessage(
          effectiveQuestion,
          chatTurn.assistant_message,
        );

      setTurns((current) =>
        current.map((turn) =>
          turn.id === turnId
            ? {
                ...turn,
                loading: false,
                streamedAnswer:
                  result.answer,
                result,
                error: "",
              }
            : turn,
        ),
      );

      window.dispatchEvent(
        new Event(
          "aqlyra:conversations-changed",
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

      const fallback =
        chatMode === "normal"
          ? "Unable to connect to the conversation service."
          : "Unable to connect to the RAG service.";

      const message =
        requestError instanceof Error
          ? requestError.message
          : fallback;

      setTurns((current) =>
        current.map((turn) =>
          turn.id === turnId
            ? {
                ...turn,
                loading: false,
                streamedAnswer:
                  chatMode === "normal"
                    ? ""
                    : turn.streamedAnswer,
                error: message,
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

  async function copyTextToClipboard(
    text: string,
  ): Promise<boolean> {
    if (
      navigator.clipboard &&
      typeof navigator.clipboard.writeText ===
        "function"
    ) {
      try {
        await navigator.clipboard.writeText(
          text,
        );

        return true;
      } catch {
        // Fall through to legacy browser fallback.
      }
    }

    const textarea =
      document.createElement("textarea");

    textarea.value = text;
    textarea.setAttribute(
      "readonly",
      "",
    );

    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    textarea.style.pointerEvents = "none";

    document.body.appendChild(
      textarea,
    );

    textarea.focus();
    textarea.select();

    let copied = false;

    try {
      copied =
        document.execCommand("copy");
    } finally {
      textarea.remove();
    }

    return copied;
  }


  async function copyAnswer(
    turnId: string,
    answer: string,
  ) {
    const copied =
      await copyTextToClipboard(
        answer,
      );

    if (!copied) {
      return;
    }

    setCopiedAnswerId(turnId);

    window.setTimeout(() => {
      setCopiedAnswerId(
        (current) =>
          current === turnId
            ? null
            : current,
      );
    }, 1500);
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
          "min-w-0 w-full rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-card-strong)] p-3 shadow-xl sm:p-4",
          centered
            ? "max-w-[760px]"
            : "max-w-[900px]",
        ].join(" ")}
      >
        {attachedDocument && (
          <div className="mb-3">
            <AttachmentPreview
              document={
                attachedDocument
              }
              previewUrl={
                attachmentPreviewUrl
              }
              removable
              onRemove={() => {
                setAttachedDocument(
                  null,
                );

                setAttachmentPreviewUrl(
                  null,
                );
              }}
            />
          </div>
        )}

        {attachmentError && (
          <div role="alert" className="mb-3 flex min-w-0 items-center gap-2 rounded-lg border border-[var(--aq-border)] px-3 py-2 text-xs text-[var(--aq-muted)]">
            <AlertCircle size={15} className="shrink-0" aria-hidden="true" />
            <span className="min-w-0 flex-1">{attachmentError}</span>
            <button
              type="button"
              aria-label="Dismiss attachment error"
              className="shrink-0 rounded-md p-1 hover:text-[var(--aq-text)]"
              onClick={() => setAttachmentError("")}
            >
              <X size={15} aria-hidden="true" />
            </button>
          </div>
        )}

        <textarea
          rows={2}
          value={question}
          disabled={ragLoading}
          onChange={(event) => {
            setQuestion(event.target.value);
            // An old attachment error must not stay pinned while chatting.
            if (attachmentError) setAttachmentError("");
          }}
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
          placeholder={
            chatMode === "normal"
              ? "Ask Aqlyra anything..."
              : "Ask Aqlyra about your documents..."
          }
          className="w-full resize-none bg-transparent text-sm leading-6 text-[var(--aq-text)] outline-none placeholder:text-[var(--aq-muted)]"
        />

        <div className="mt-3 flex min-w-0 items-center gap-2 sm:gap-3">
          <ChatToolsMenu
            mode={chatMode}
            disabled={ragLoading || uploadState !== "idle"}
            onUpload={() => fileInputRef.current?.click()}
            onOpenDocuments={() => {
              setEvidenceDrawerOpen(false);
              setDocumentDrawerOpen(true);
            }}
            onSwitchMode={() => switchChatMode(
              chatMode === "knowledge" ? "normal" : "knowledge",
            )}
          />

          {chatMode === "normal" && (
            <select
              aria-label="Web search mode"
              title="Choose how Aqlyra searches public websites"
              value={webMode}
              onChange={(event) => setWebMode(event.target.value as typeof webMode)}
              disabled={ragLoading || uploadState !== "idle"}
              className="min-w-0 max-w-[104px] rounded-lg border border-[var(--aq-border)] bg-[var(--aq-control)] px-1.5 py-2 text-[10px] font-semibold text-[var(--aq-text)] focus-visible:outline-2 focus-visible:outline-[var(--aq-blue)]"
            >
              <option value="auto">Web: Auto</option>
              <option value="on">Web: On</option>
              <option value="deep">Deep web</option>
              <option value="off">Web: Off</option>
            </select>
          )}

          {uploadState !==
            "idle" && (
            <span className="text-[10px] text-[var(--aq-muted)]">
              {uploadState ===
              "uploading"
                ? "Uploading..."
                : "Processing..."}
            </span>
          )}

          <div className="ml-auto flex shrink-0 items-center gap-2">
            <VoiceCallButton
              mode={chatMode}
              conversationId={
                chatMode === "normal"
                  ? normalConversationId
                  : knowledgeConversationId
              }
              documentIds={
                attachedDocument
                  ? [
                      attachedDocument.id,
                    ]
                  : []
              }
              disabled={
                ragLoading ||
                uploadState !== "idle"
              }
              onConversationStarted={(
                conversationId,
              ) => {
                voiceConversationIdRef
                  .current =
                    conversationId;

                if (
                  chatMode ===
                  "normal"
                ) {
                  setNormalConversationId(
                    conversationId,
                  );
                } else {
                  setKnowledgeConversationId(
                    conversationId,
                  );
                }

                window.dispatchEvent(
                  new Event(
                    "aqlyra:conversations-changed",
                  ),
                );
              }}
              onUserTranscript={(
                text,
              ) => {
                setQuestion(
                  text,
                );
              }}
              onAgentTranscript={(
                _text,
                isFinal,
              ) => {
                if (!isFinal) {
                  return;
                }

                const conversationId =
                  voiceConversationIdRef
                    .current;

                if (!conversationId) {
                  return;
                }

                void refreshVoiceConversation(
                  conversationId,
                );
              }}
            />

            <button
              type="submit"
              disabled={
                ragLoading ||
                uploadState !== "idle" ||
                !question.trim() &&
                !attachedDocument
              }
              className="flex h-10 items-center gap-2 rounded-xl bg-[var(--aq-blue)] px-3 text-xs font-semibold text-white transition hover:bg-[var(--aq-blue-hover)] disabled:cursor-not-allowed disabled:opacity-50 sm:px-5"
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
    <div className="relative flex h-full min-h-0 min-w-0 w-full overflow-hidden">
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.xlsx,.pptx,.txt,.md,.csv,.png,.jpg,.jpeg,.webp"
        className="hidden"
        onChange={
          handleAttachmentChange
        }
      />

      <section
        className={[
          "aq-panel flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden transition-[padding] duration-200",
          evidenceDrawerOpen
            ? "lg:pr-[400px]"
            : "",
        ].join(" ")}
      >
        <div className="flex h-14 min-w-0 shrink-0 items-center border-b border-[var(--aq-border)] px-2 sm:px-4">
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
            className="flex h-9 shrink-0 items-center gap-2 rounded-lg border border-[var(--aq-border)] bg-[var(--aq-card)] px-2 text-xs font-semibold sm:px-3"
          >
            <PanelLeft
              size={15}
            />

            Documents
          </button>

          <div className="ml-2 hidden items-center gap-2 sm:flex">
            <Sparkles
              size={16}
              className="text-[var(--aq-cyan)]"
            />

            <span className="text-sm font-semibold">
              Aqlyra
            </span>
          </div>

          <div className="ml-auto flex shrink-0 items-center rounded-full border border-[var(--aq-border)] bg-[var(--aq-card)] p-0.5 sm:p-1">
            <button
              type="button"
              disabled={ragLoading}
              onClick={() =>
                switchChatMode(
                  "normal",
                )
              }
              className={[
                "rounded-full px-2 py-1 text-[10px] font-semibold transition sm:px-3",
                chatMode === "normal"
                  ? "bg-[var(--aq-blue)] text-white"
                  : "text-[var(--aq-muted)] hover:text-[var(--aq-text)]",
              ].join(" ")}
            >
              Converse
            </button>

            <button
              type="button"
              disabled={ragLoading}
              onClick={() =>
                switchChatMode(
                  "knowledge",
                )
              }
              className={[
                "rounded-full px-2 py-1 text-[10px] font-semibold transition sm:px-3",
                chatMode === "knowledge"
                  ? "bg-[var(--aq-blue)] text-white"
                  : "text-[var(--aq-muted)] hover:text-[var(--aq-text)]",
              ].join(" ")}
            >
              Knowledge
            </button>
          </div>
        </div>

        {!hasConversation ? (
          <div className="flex min-h-0 min-w-0 flex-1 items-center justify-center px-3 pb-4 sm:px-6 sm:pb-12">
            <div className="flex w-full max-w-[760px] flex-col items-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-card)] text-[var(--aq-blue)]">
                <Sparkles
                  size={21}
                />
              </div>

              <h2 className="mt-5 text-xl font-semibold">
                {chatMode === "normal"
                  ? "Chat with Aqlyra"
                  : "Ask your knowledge base"}
              </h2>

              <p className="mt-2 max-w-[500px] text-center text-sm leading-6 text-[var(--aq-muted)]">
                {chatMode === "normal"
                  ? "Ask general questions and continue a memory-aware conversation."
                  : "Upload a document or ask a grounded question across your processed knowledge sources."}
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
            <div className="aq-scrollbar min-h-0 min-w-0 flex-1 overflow-y-auto px-3 py-4 sm:px-6 sm:py-8">
              <div className="mx-auto w-full max-w-[820px] space-y-10">
                {turns.map(
                  (turn) => (
                    <div
                      key={turn.id}
                    >
                      <div className="ml-auto flex max-w-[560px] flex-col items-end gap-2">
                        {turn.attachment && (
                          <AttachmentPreview
                            document={
                              turn
                                .attachment
                                .document
                            }
                            previewUrl={
                              turn
                                .attachment
                                .previewUrl
                            }
                            compact
                          />
                        )}

                        {turn.question && (
                          <div className="max-w-full rounded-2xl bg-[var(--aq-blue)] px-5 py-4 text-sm leading-6 text-white">
                            {
                              turn.question
                            }
                          </div>
                        )}
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

                        {turn.loading &&
                          !turn.streamedAnswer && (
                          <div className="flex items-center gap-3 rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-card-strong)] p-5">
                            <LoaderCircle
                              size={17}
                              className="animate-spin text-[var(--aq-blue)]"
                            />

                            <span className="text-xs text-[var(--aq-muted)]">
                              {turn.mode === "normal"
                                ? "Aqlyra is thinking..."
                                : "Retrieving evidence..."}
                            </span>
                          </div>
                        )}

                        {turn.streamedAnswer &&
                          !turn.result && !turn.artifacts?.length && (
                          <div className="rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-card-strong)] p-5">
                            <MarkdownMessage
                              content={turn.streamedAnswer}
                              isStreaming={turn.loading}
                            />
                          </div>
                        )}

                        {turn.artifacts && turn.artifacts.length > 0 && (
                          <div className="rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-card-strong)] p-5">
                            <p className="mb-3 text-sm font-semibold">
                              {turn.streamedAnswer || "Files ready"}
                            </p>
                            <div className="space-y-2">
                              {turn.artifacts.map(file => (
                                <a
                                  key={file.id}
                                  href={"/api/artifacts/" + encodeURIComponent(file.id) + "/download"}
                                  className="flex items-center gap-3 rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] p-3 text-xs hover:border-[var(--aq-blue)]"
                                >
                                  <FilePlus2 size={18} className="shrink-0 text-[var(--aq-blue)]" />
                                  <span className="min-w-0 flex-1 truncate">{file.filename}</span>
                                  <Download size={17} className="shrink-0" />
                                </a>
                              ))}
                            </div>
                          </div>
                        )}

                        {turn.error && (
                          <div className="flex gap-3 rounded-2xl border border-red-500/30 bg-red-500/10 p-5">
                            <AlertCircle
                              size={17}
                              className="text-red-400"
                            />

                            <div className="min-w-0 flex-1">
                              <p className="text-xs text-red-300">
                                {turn.error}
                              </p>
                              {turn.mode === "knowledge" &&
                                turn.error.toLowerCase().includes("embedding service quota") && (
                                <button
                                  type="button"
                                  className="mt-3 rounded-lg border border-[var(--aq-border)] px-3 py-2 text-xs font-semibold text-[var(--aq-text)]"
                                  onClick={() => {
                                    switchChatMode("normal");
                                    setQuestion(turn.question);
                                  }}
                                >
                                  Switch to Normal chat (without document search)
                                </button>
                              )}
                            </div>
                          </div>
                        )}

                        {turn.result && (
                          <div className="rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-card-strong)] p-5">
                            <MarkdownMessage
                              content={
                                turn.result
                                  .answer
                              }
                            />

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

                            <div className="mt-5 flex items-center justify-end border-t border-[var(--aq-border)] pt-4">

                              <button
                                type="button"
                                onClick={() => {
                                  void copyAnswer(
                                    turn.id,
                                    turn.result!
                                      .answer,
                                  );
                                }}
                                className="flex h-8 items-center gap-2 rounded-lg border border-[var(--aq-border)] bg-[var(--aq-control)] px-3 text-[10px] font-semibold"
                              >
                                <Copy
                                  size={12}
                                />

                                {copiedAnswerId ===
                                turn.id
                                  ? "Copied"
                                  : "Copy"}
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

            <div className="min-w-0 shrink-0 px-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-2 sm:px-5 sm:pb-5">
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

          <aside className="absolute inset-y-0 left-0 z-30 flex w-[min(100%,360px)] max-w-full flex-col border-r border-[var(--aq-border)] bg-[var(--aq-bg-deep)] shadow-2xl">
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
          <aside className="absolute inset-y-0 right-0 z-30 flex w-[min(100%,400px)] max-w-full flex-col border-l border-[var(--aq-border)] bg-[var(--aq-bg-deep)] shadow-2xl">
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
