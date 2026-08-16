"use client";

import {
  MoreHorizontal,
  Pencil,
  Pin,
  PinOff,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useState,
} from "react";

import type {
  ConversationMode,
  ConversationResponse,
} from "@/types/conversation";

type ApiError = {
  detail?: unknown;
};

function isConversation(
  value: ConversationResponse | ApiError,
): value is ConversationResponse {
  return (
    "id" in value &&
    typeof value.id === "string"
  );
}

export function ConversationHistory() {
  const [
    conversations,
    setConversations,
  ] = useState<ConversationResponse[]>([]);

  const [
    activeMode,
    setActiveMode,
  ] = useState<ConversationMode>(
    "normal",
  );

  const [
    menuConversationId,
    setMenuConversationId,
  ] = useState<string | null>(null);

  const loadConversations =
    useCallback(async () => {
      try {
        const response =
          await fetch(
            "/api/conversations",
            {
              cache: "no-store",
            },
          );

        const data =
          (await response.json()) as
            | ConversationResponse[]
            | ApiError;

        if (
          !response.ok ||
          !Array.isArray(data)
        ) {
          return;
        }

        setConversations(data);
      } catch {
        // History remains available on the next refresh.
      }
    }, []);

  useEffect(() => {
    const initialLoadTimer =
      window.setTimeout(() => {
        void loadConversations();
      }, 0);

    function refreshHistory() {
      void loadConversations();
    }

    function closeMenus() {
      setMenuConversationId(null);
    }

    function handleModeChanged(
      event: Event,
    ) {
      const detail =
        (
          event as CustomEvent<{
            mode?: ConversationMode;
          }>
        ).detail;

      if (
        detail?.mode === "normal" ||
        detail?.mode === "knowledge"
      ) {
        setActiveMode(
          detail.mode,
        );

        setMenuConversationId(
          null,
        );
      }
    }

    window.addEventListener(
      "aqlyra:chat-mode-changed",
      handleModeChanged,
    );

    window.addEventListener(
      "aqlyra:conversations-changed",
      refreshHistory,
    );

    window.addEventListener(
      "aqlyra:new-chat",
      closeMenus,
    );

    return () => {
      window.clearTimeout(
        initialLoadTimer,
      );

      window.removeEventListener(
        "aqlyra:chat-mode-changed",
        handleModeChanged,
      );

      window.removeEventListener(
        "aqlyra:conversations-changed",
        refreshHistory,
      );

      window.removeEventListener(
        "aqlyra:new-chat",
        closeMenus,
      );
    };
  }, [loadConversations]);

  function openConversation(
    conversation: ConversationResponse,
  ) {
    setMenuConversationId(null);

    window.dispatchEvent(
      new CustomEvent(
        "aqlyra:open-conversation",
        {
          detail: {
            id: conversation.id,
            title: conversation.title,
            mode: conversation.mode,
          },
        },
      ),
    );
  }

  async function patchConversation(
    conversationId: string,
    body: {
      title?: string;
      is_pinned?: boolean;
    },
  ) {
    try {
      const response =
        await fetch(
          `/api/conversations/${encodeURIComponent(
            conversationId,
          )}`,
          {
            method: "PATCH",
            headers: {
              "Content-Type":
                "application/json",
            },
            body: JSON.stringify(body),
          },
        );

      const data =
        (await response.json()) as
          | ConversationResponse
          | ApiError;

      if (
        !response.ok ||
        !isConversation(data)
      ) {
        return;
      }

      await loadConversations();
    } catch {
      // Leave the existing history unchanged.
    }
  }

  async function renameConversation(
    conversation: ConversationResponse,
  ) {
    setMenuConversationId(null);

    const nextTitle =
      window.prompt(
        "Rename conversation",
        conversation.title,
      );

    if (nextTitle === null) {
      return;
    }

    const cleaned =
      nextTitle.trim();

    if (
      !cleaned ||
      cleaned === conversation.title
    ) {
      return;
    }

    await patchConversation(
      conversation.id,
      {
        title: cleaned,
      },
    );
  }

  async function togglePin(
    conversation: ConversationResponse,
  ) {
    setMenuConversationId(null);

    await patchConversation(
      conversation.id,
      {
        is_pinned:
          !conversation.is_pinned,
      },
    );
  }

  const visibleConversations =
    conversations.filter(
      (conversation) =>
        conversation.mode ===
        activeMode,
    );

  const pinned =
    visibleConversations.filter(
      (conversation) =>
        conversation.is_pinned,
    );

  const history =
    visibleConversations.filter(
      (conversation) =>
        !conversation.is_pinned,
    );

  function renderConversation(
    conversation: ConversationResponse,
  ) {
    const menuOpen =
      menuConversationId ===
      conversation.id;

    return (
      <div
        key={conversation.id}
        className="group relative flex min-w-0 items-center rounded-lg hover:bg-[var(--aq-card)]"
      >
        <button
          type="button"
          title={conversation.title}
          onClick={() =>
            openConversation(
              conversation,
            )
          }
          className="min-w-0 flex-1 truncate px-3 py-2 text-left text-[11px] text-[var(--aq-muted)] transition group-hover:text-[var(--aq-text)]"
        >
          {conversation.title}
        </button>

        <button
          type="button"
          aria-label={`Conversation options for ${conversation.title}`}
          onClick={() =>
            setMenuConversationId(
              menuOpen
                ? null
                : conversation.id,
            )
          }
          className="mr-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-[var(--aq-muted)] opacity-70 transition hover:bg-[var(--aq-control)] hover:text-[var(--aq-text)] group-hover:opacity-100"
        >
          <MoreHorizontal
            size={14}
          />
        </button>

        {menuOpen && (
          <div className="absolute right-1 top-9 z-50 w-36 rounded-xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-1.5 shadow-2xl">
            <button
              type="button"
              onClick={() => {
                void renameConversation(
                  conversation,
                );
              }}
              className="flex h-9 w-full items-center gap-2 rounded-lg px-2.5 text-left text-[10px] transition hover:bg-[var(--aq-control)]"
            >
              <Pencil size={13} />
              Rename
            </button>

            <button
              type="button"
              onClick={() => {
                void togglePin(
                  conversation,
                );
              }}
              className="flex h-9 w-full items-center gap-2 rounded-lg px-2.5 text-left text-[10px] transition hover:bg-[var(--aq-control)]"
            >
              {conversation.is_pinned ? (
                <PinOff size={13} />
              ) : (
                <Pin size={13} />
              )}

              {conversation.is_pinned
                ? "Unpin"
                : "Pin"}
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="mt-6 space-y-5">
      {pinned.length > 0 && (
        <section>
          <p className="mb-1 px-3 text-[9px] font-semibold uppercase tracking-[0.14em] text-[var(--aq-muted)]">
            Pinned
          </p>

          <div className="space-y-0.5">
            {pinned.map(
              renderConversation,
            )}
          </div>
        </section>
      )}

      <section>
        <p className="mb-1 px-3 text-[9px] font-semibold uppercase tracking-[0.14em] text-[var(--aq-muted)]">
          History
        </p>

        {history.length > 0 ? (
          <div className="space-y-0.5">
            {history.map(
              renderConversation,
            )}
          </div>
        ) : (
          pinned.length === 0 && (
            <p className="px-3 py-2 text-[10px] text-[var(--aq-muted)]">
              No chat history yet
            </p>
          )
        )}
      </section>
    </div>
  );
}
