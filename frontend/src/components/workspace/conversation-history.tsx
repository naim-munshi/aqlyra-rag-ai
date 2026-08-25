"use client";

import {
  ChevronDown,
  ChevronRight,
  Copy,
  Folder,
  FolderPlus,
  MoreHorizontal,
  Pencil,
  Pin,
  PinOff,
  Trash2,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useState,
} from "react";

import type {
  ConversationMessageResponse,
  ConversationMode,
  ConversationResponse,
} from "@/types/conversation";
import type {
  ProjectResponse,
} from "@/types/project";


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


function isProject(
  value: ProjectResponse | ApiError,
): value is ProjectResponse {
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
    projects,
    setProjects,
  ] = useState<ProjectResponse[]>([]);

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

  const [
    menuProjectId,
    setMenuProjectId,
  ] = useState<string | null>(null);

  const [
    collapsedProjectIds,
    setCollapsedProjectIds,
  ] = useState<Set<string>>(
    () => new Set<string>(),
  );

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
        // Keep the current sidebar state.
      }
    }, []);

  const loadProjects =
    useCallback(async () => {
      try {
        const response =
          await fetch(
            "/api/projects",
            {
              cache: "no-store",
            },
          );

        const data =
          (await response.json()) as
            | ProjectResponse[]
            | ApiError;

        if (
          !response.ok ||
          !Array.isArray(data)
        ) {
          return;
        }

        setProjects(data);
      } catch {
        // Keep the current sidebar state.
      }
    }, []);

  useEffect(() => {
    const initialLoadTimer =
      window.setTimeout(() => {
        void loadConversations();
        void loadProjects();
      }, 0);

    function refreshConversations() {
      void loadConversations();
    }

    function refreshProjects() {
      void loadProjects();
      void loadConversations();
    }

    function closeMenus() {
      setMenuConversationId(null);
      setMenuProjectId(null);
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
        setActiveMode(detail.mode);
        closeMenus();
      }
    }

    window.addEventListener(
      "aqlyra:chat-mode-changed",
      handleModeChanged,
    );
    window.addEventListener(
      "aqlyra:conversations-changed",
      refreshConversations,
    );
    window.addEventListener(
      "aqlyra:projects-changed",
      refreshProjects,
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
        refreshConversations,
      );
      window.removeEventListener(
        "aqlyra:projects-changed",
        refreshProjects,
      );
      window.removeEventListener(
        "aqlyra:new-chat",
        closeMenus,
      );
    };
  }, [
    loadConversations,
    loadProjects,
  ]);

  function openConversation(
    conversation: ConversationResponse,
  ) {
    setMenuConversationId(null);
    setMenuProjectId(null);

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
      project_id?: string | null;
    },
  ): Promise<boolean> {
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
        return false;
      }

      await loadConversations();
      return true;
    } catch {
      return false;
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
      { title: cleaned },
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

  async function moveConversation(
    conversation: ConversationResponse,
    projectId: string | null,
  ) {
    setMenuConversationId(null);

    await patchConversation(
      conversation.id,
      { project_id: projectId },
    );
  }

  async function copyConversation(
    conversation: ConversationResponse,
  ) {
    setMenuConversationId(null);

    try {
      const response =
        await fetch(
          `/api/conversations/${encodeURIComponent(
            conversation.id,
          )}/messages`,
          {
            cache: "no-store",
          },
        );

      const data =
        (await response.json()) as
          | ConversationMessageResponse[]
          | ApiError;

      if (
        !response.ok ||
        !Array.isArray(data)
      ) {
        return;
      }

      const transcript =
        data
          .map((message) => {
            const speaker =
              message.role === "user"
                ? "You"
                : "Aqlyra";

            return (
              `${speaker}:\n` +
              message.content
            );
          })
          .join("\n\n");

      if (!transcript) {
        return;
      }

      await navigator.clipboard
        .writeText(transcript);
    } catch {
      // Clipboard failure is non-destructive.
    }
  }

  async function deleteConversation(
    conversation: ConversationResponse,
  ) {
    setMenuConversationId(null);

    const confirmed =
      window.confirm(
        `Delete "${conversation.title}"?

` +
        "This conversation and its messages " +
        "will be permanently deleted.",
      );

    if (!confirmed) {
      return;
    }

    try {
      const response =
        await fetch(
          `/api/conversations/${encodeURIComponent(
            conversation.id,
          )}`,
          {
            method: "DELETE",
          },
        );

      if (!response.ok) {
        return;
      }

      setConversations(
        (current) =>
          current.filter(
            (item) =>
              item.id !==
              conversation.id,
          ),
      );

      window.dispatchEvent(
        new CustomEvent(
          "aqlyra:conversation-deleted",
          {
            detail: {
              id: conversation.id,
            },
          },
        ),
      );

      window.dispatchEvent(
        new Event(
          "aqlyra:conversations-changed",
        ),
      );

      await loadConversations();
    } catch {
      // Keep current history unchanged.
    }
  }

  async function renameProject(
    project: ProjectResponse,
  ) {
    setMenuProjectId(null);

    const nextName =
      window.prompt(
        "Rename project",
        project.name,
      );

    if (nextName === null) {
      return;
    }

    const name =
      nextName.trim();

    if (
      !name ||
      name === project.name
    ) {
      return;
    }

    try {
      const response =
        await fetch(
          `/api/projects/${encodeURIComponent(
            project.id,
          )}`,
          {
            method: "PATCH",
            headers: {
              "Content-Type":
                "application/json",
            },
            body: JSON.stringify({
              name,
            }),
          },
        );

      const data =
        (await response.json()) as
          | ProjectResponse
          | ApiError;

      if (
        !response.ok ||
        !isProject(data)
      ) {
        return;
      }

      await loadProjects();
    } catch {
      // Keep current project state.
    }
  }

  async function deleteProject(
    project: ProjectResponse,
  ) {
    setMenuProjectId(null);

    const confirmed =
      window.confirm(
        `Delete project "${project.name}"?

` +
        "Chats in this project will return " +
        "to regular History.",
      );

    if (!confirmed) {
      return;
    }

    try {
      const response =
        await fetch(
          `/api/projects/${encodeURIComponent(
            project.id,
          )}`,
          {
            method: "DELETE",
          },
        );

      if (!response.ok) {
        return;
      }

      setProjects(
        (current) =>
          current.filter(
            (item) =>
              item.id !==
              project.id,
          ),
      );

      await loadConversations();
    } catch {
      // Keep current project state.
    }
  }

  function toggleProject(
    projectId: string,
  ) {
    setCollapsedProjectIds(
      (current) => {
        const next =
          new Set(current);

        if (next.has(projectId)) {
          next.delete(projectId);
        } else {
          next.add(projectId);
        }

        return next;
      },
    );
  }

  const visibleConversations =
    conversations.filter(
      (conversation) =>
        conversation.mode ===
        activeMode,
    );

  const visibleProjects =
    projects.filter(
      (project) =>
        project.mode ===
        activeMode,
    );

  const regularConversations =
    visibleConversations.filter(
      (conversation) =>
        conversation.project_id === null,
    );

  const pinned =
    regularConversations.filter(
      (conversation) =>
        conversation.is_pinned,
    );

  const history =
    regularConversations.filter(
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
          onClick={() => {
            setMenuProjectId(null);
            setMenuConversationId(
              menuOpen
                ? null
                : conversation.id,
            );
          }}
          className="mr-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-[var(--aq-muted)] opacity-70 transition hover:bg-[var(--aq-control)] hover:text-[var(--aq-text)] group-hover:opacity-100"
        >
          <MoreHorizontal size={14} />
        </button>

        {menuOpen && (
          <div className="absolute right-1 top-9 z-50 w-48 rounded-xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-1.5 shadow-2xl">
            <button
              type="button"
              onClick={() => {
                void copyConversation(
                  conversation,
                );
              }}
              className="flex h-9 w-full items-center gap-2 rounded-lg px-2.5 text-left text-[10px] transition hover:bg-[var(--aq-control)]"
            >
              <Copy size={13} />
              Copy conversation
            </button>

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

            <div className="my-1 border-t border-[var(--aq-border)]" />

            <div className="px-2.5 py-1.5">
              <label
                htmlFor={`project-${conversation.id}`}
                className="mb-1 flex items-center gap-1.5 text-[9px] font-semibold text-[var(--aq-muted)]"
              >
                <FolderPlus size={12} />
                {conversation.project_id
                  ? "Move to project"
                  : "Add to project"}
              </label>

              {visibleProjects.length > 0 ? (
                <select
                  id={`project-${conversation.id}`}
                  value={
                    conversation.project_id
                    ?? ""
                  }
                  onChange={(event) => {
                    const projectId =
                      event.target.value
                        || null;

                    void moveConversation(
                      conversation,
                      projectId,
                    );
                  }}
                  className="h-8 w-full rounded-lg border border-[var(--aq-border)] bg-[var(--aq-card)] px-2 text-[10px] text-[var(--aq-text)] outline-none"
                >
                  <option
                    value=""
                    disabled={
                      conversation.project_id
                      === null
                    }
                  >
                    {conversation.project_id
                      ? "Remove from project"
                      : "Choose a project"}
                  </option>

                  {visibleProjects.map(
                    (project) => (
                      <option
                        key={project.id}
                        value={project.id}
                      >
                        {project.name}
                      </option>
                    ),
                  )}
                </select>
              ) : (
                <p className="py-1 text-[9px] text-[var(--aq-muted)]">
                  Create a project first
                </p>
              )}
            </div>

            <div className="my-1 border-t border-[var(--aq-border)]" />

            <button
              type="button"
              onClick={() => {
                void deleteConversation(
                  conversation,
                );
              }}
              className="flex h-9 w-full items-center gap-2 rounded-lg px-2.5 text-left text-[10px] text-red-400 transition hover:bg-red-500/10"
            >
              <Trash2 size={13} />
              Delete
            </button>
          </div>
        )}
      </div>
    );
  }

  function renderProject(
    project: ProjectResponse,
  ) {
    const collapsed =
      collapsedProjectIds.has(
        project.id,
      );

    const projectMenuOpen =
      menuProjectId === project.id;

    const projectConversations =
      visibleConversations.filter(
        (conversation) =>
          conversation.project_id ===
          project.id,
      );

    return (
      <div
        key={project.id}
        className="relative"
      >
        <div className="group flex items-center rounded-lg hover:bg-[var(--aq-card)]">
          <button
            type="button"
            onClick={() =>
              toggleProject(project.id)
            }
            className="flex min-w-0 flex-1 items-center gap-2 px-2 py-2 text-left"
          >
            {collapsed ? (
              <ChevronRight
                size={12}
                className="shrink-0 text-[var(--aq-muted)]"
              />
            ) : (
              <ChevronDown
                size={12}
                className="shrink-0 text-[var(--aq-muted)]"
              />
            )}

            <Folder
              size={13}
              className="shrink-0 text-[var(--aq-blue)]"
            />

            <span className="min-w-0 flex-1 truncate text-[11px] font-medium">
              {project.name}
            </span>

            <span className="text-[9px] text-[var(--aq-muted)]">
              {projectConversations.length}
            </span>
          </button>

          <button
            type="button"
            aria-label={`Project options for ${project.name}`}
            onClick={() => {
              setMenuConversationId(null);
              setMenuProjectId(
                projectMenuOpen
                  ? null
                  : project.id,
              );
            }}
            className="mr-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-[var(--aq-muted)] opacity-70 transition hover:bg-[var(--aq-control)] hover:text-[var(--aq-text)] group-hover:opacity-100"
          >
            <MoreHorizontal size={14} />
          </button>
        </div>

        {projectMenuOpen && (
          <div className="absolute right-1 top-9 z-50 w-40 rounded-xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-1.5 shadow-2xl">
            <button
              type="button"
              onClick={() => {
                void renameProject(
                  project,
                );
              }}
              className="flex h-9 w-full items-center gap-2 rounded-lg px-2.5 text-left text-[10px] transition hover:bg-[var(--aq-control)]"
            >
              <Pencil size={13} />
              Rename
            </button>

            <div className="my-1 border-t border-[var(--aq-border)]" />

            <button
              type="button"
              onClick={() => {
                void deleteProject(
                  project,
                );
              }}
              className="flex h-9 w-full items-center gap-2 rounded-lg px-2.5 text-left text-[10px] text-red-400 transition hover:bg-red-500/10"
            >
              <Trash2 size={13} />
              Delete project
            </button>
          </div>
        )}

        {!collapsed && (
          <div className="ml-4 border-l border-[var(--aq-border)] pl-1">
            {projectConversations.length > 0 ? (
              projectConversations.map(
                renderConversation,
              )
            ) : (
              <p className="px-3 py-1.5 text-[9px] text-[var(--aq-muted)]">
                No chats yet
              </p>
            )}
          </div>
        )}
      </div>
    );
  }

  const modeLabel =
    activeMode === "normal"
      ? "Converse"
      : "Knowledge";

  return (
    <div className="mt-6 space-y-5">
      <section>
        <p className="mb-1 px-3 text-[9px] font-semibold uppercase tracking-[0.14em] text-[var(--aq-muted)]">
          {modeLabel} projects
        </p>

        {visibleProjects.length > 0 ? (
          <div className="space-y-0.5">
            {visibleProjects.map(
              renderProject,
            )}
          </div>
        ) : (
          <p className="px-3 py-2 text-[10px] text-[var(--aq-muted)]">
            No projects yet
          </p>
        )}
      </section>

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
              No regular chat history yet
            </p>
          )
        )}
      </section>
    </div>
  );
}
