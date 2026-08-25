"use client";

import {
  useEffect,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import {
  ChevronDown,
  CircleHelp,
  FileText,
  FolderPlus,
  LogOut,
  MessageSquareText,
  Plus,
  Settings,
  Sparkles,
} from "lucide-react";

import { AqlyraLogo } from "@/components/brand/aqlyra-logo";
import { ThemeSettings } from "@/components/theme/theme-settings";
import { ConversationHistory } from "@/components/workspace/conversation-history";
import type { UserResponse } from "@/types/auth";
import type {
  ConversationMode,
} from "@/types/conversation";


type SidebarProps = {
  user: UserResponse;
};


export function Sidebar({
  user,
}: SidebarProps) {
  const router = useRouter();

  const [settingsOpen, setSettingsOpen] =
    useState(false);

  const [
    profileMenuOpen,
    setProfileMenuOpen,
  ] = useState(false);

  const [
    activeMode,
    setActiveMode,
  ] = useState<ConversationMode>(
    "normal",
  );

  useEffect(() => {
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
      }
    }

    window.addEventListener(
      "aqlyra:chat-mode-changed",
      handleModeChanged,
    );

    return () => {
      window.removeEventListener(
        "aqlyra:chat-mode-changed",
        handleModeChanged,
      );
    };
  }, []);

  function startNewChat() {
    setProfileMenuOpen(false);

    window.dispatchEvent(
      new Event("aqlyra:new-chat"),
    );
  }

  async function createProject() {
    setProfileMenuOpen(false);

    const modeLabel =
      activeMode === "normal"
        ? "Converse"
        : "Knowledge";

    const projectName =
      window.prompt(
        `New ${modeLabel} project`,
      );

    if (projectName === null) {
      return;
    }

    const name =
      projectName.trim();

    if (!name) {
      return;
    }

    try {
      const response = await fetch(
        "/api/projects",
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            name,
            mode: activeMode,
          }),
        },
      );

      if (!response.ok) {
        window.alert(
          "Unable to create project.",
        );
        return;
      }

      window.dispatchEvent(
        new Event(
          "aqlyra:projects-changed",
        ),
      );
    } catch {
      window.alert(
        "Unable to create project.",
      );
    }
  }

  function openDocuments() {
    window.dispatchEvent(
      new Event("aqlyra:open-documents"),
    );
  }

  function focusChat() {
    window.dispatchEvent(
      new Event("aqlyra:focus-chat"),
    );
  }

  function openSettings() {
    setProfileMenuOpen(false);
    setSettingsOpen(true);
  }

  async function handleLogout() {
    setProfileMenuOpen(false);

    try {
      await fetch("/api/auth/logout", {
        method: "POST",
      });
      router.replace("/login");
      router.refresh();
    } catch {
      router.replace("/login");
      router.refresh();
    }
  }

  return (
    <>
      <aside className="aq-scrollbar flex h-screen w-[244px] shrink-0 flex-col overflow-y-auto border-r border-[var(--aq-border)] bg-[var(--aq-bg-deep)] px-4 py-5">
        <div className="px-2">
          <AqlyraLogo size={46} />
        </div>

        <div className="mt-7 space-y-2">
          <button
            type="button"
            onClick={() => {
              void createProject();
            }}
            title={`Create a ${
              activeMode === "normal"
                ? "Converse"
                : "Knowledge"
            } project`}
            className="flex h-11 w-full items-center gap-3 rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] px-4 text-sm font-semibold text-[var(--aq-text)] transition hover:bg-[var(--aq-control)]"
          >
            <FolderPlus
              size={18}
              strokeWidth={1.8}
            />
            <span className="flex-1 text-left">
              New project
            </span>
          </button>

          <button
            type="button"
            onClick={startNewChat}
            className="flex h-11 w-full items-center gap-3 rounded-xl bg-[var(--aq-blue)] px-4 text-sm font-semibold text-white transition hover:bg-[var(--aq-blue-hover)]"
          >
            <Plus
              size={18}
              strokeWidth={2}
            />

            New chat
          </button>
        </div>

        <ConversationHistory />

        <nav className="mt-6 space-y-1">
          <button
            type="button"
            onClick={openDocuments}
            className="flex h-11 w-full items-center gap-3 rounded-xl px-3 text-sm text-[var(--aq-muted)] transition hover:bg-[var(--aq-card)] hover:text-[var(--aq-text)]"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-full border border-[var(--aq-border)] bg-[var(--aq-panel)]">
              <FileText size={15} />
            </span>
            Documents
          </button>

          <button
            type="button"
            onClick={focusChat}
            className="flex h-11 w-full items-center gap-3 rounded-xl bg-[var(--aq-blue-muted)] px-3 text-sm font-semibold"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--aq-blue)] text-white">
              <MessageSquareText
                size={15}
              />
            </span>
            RAG Chat
          </button>
        </nav>

        <div className="mt-auto pt-5">
          <div className="rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-4">
            <div className="flex items-center gap-2">
              <Sparkles
                size={16}
                className="text-[var(--aq-cyan)]"
              />

              <p className="text-sm font-bold">
                Aqlyra Plus
              </p>
            </div>

            <p className="mt-3 text-xs leading-5 text-[var(--aq-muted)]">
              Higher limits and premium workspace
              features.
            </p>

            <button
              type="button"
              className="mt-4 h-10 w-full rounded-xl bg-[var(--aq-blue)] text-xs font-semibold text-white transition hover:bg-[var(--aq-blue-hover)]"
            >
              Upgrade
            </button>
          </div>

          <div className="relative mt-4">
            {profileMenuOpen && (
              <div className="absolute bottom-[calc(100%+10px)] left-0 right-0 z-40 overflow-hidden rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-2 shadow-2xl">
                <div className="border-b border-[var(--aq-border)] px-3 pb-3 pt-2">
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--aq-blue)] text-xs font-bold text-white">
                      {user.username
                        .slice(0, 1)
                        .toUpperCase()}
                    </div>

                    <div className="min-w-0">
                      <p className="truncate text-xs font-semibold">
                        {user.username}
                      </p>

                      <p className="mt-1 truncate text-[9px] text-[var(--aq-muted)]">
                        {user.email}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="py-2">
                  <button
                    type="button"
                    onClick={() =>
                      setProfileMenuOpen(false)
                    }
                    className="flex h-10 w-full items-center gap-3 rounded-lg px-3 text-left text-xs transition hover:bg-[var(--aq-control)]"
                  >
                    <Sparkles
                      size={15}
                      className="text-[var(--aq-cyan)]"
                    />
                    Upgrade plan
                  </button>

                  <button
                    type="button"
                    onClick={openSettings}
                    className="flex h-10 w-full items-center gap-3 rounded-lg px-3 text-left text-xs transition hover:bg-[var(--aq-control)]"
                  >
                    <Settings size={15} />
                    Settings
                  </button>

                  <button
                    type="button"
                    onClick={() =>
                      setProfileMenuOpen(false)
                    }
                    className="flex h-10 w-full items-center gap-3 rounded-lg px-3 text-left text-xs transition hover:bg-[var(--aq-control)]"
                  >
                    <CircleHelp size={15} />
                    Help
                  </button>
                </div>

                <div className="border-t border-[var(--aq-border)] pt-2">
                  <button
                    type="button"
                    onClick={() => {
                      void handleLogout();
                    }}
                    className="flex h-10 w-full items-center gap-3 rounded-lg px-3 text-left text-xs transition hover:bg-[var(--aq-control)]"
                  >
                    <LogOut size={15} />
                    Sign out
                  </button>
                </div>
              </div>
            )}

            <button
              type="button"
              aria-expanded={profileMenuOpen}
              onClick={() =>
                setProfileMenuOpen(
                  (current) => !current,
                )
              }
              className="flex w-full items-center gap-3 rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] p-3 text-left transition hover:bg-[var(--aq-control)]"
            >
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--aq-blue)] text-xs font-bold text-white">
                {user.username
                  .slice(0, 1)
                  .toUpperCase()}
              </div>

              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-semibold">
                  {user.username}
                </p>

                <p className="mt-1 truncate text-[9px] text-[var(--aq-muted)]">
                  {user.email}
                </p>
              </div>

              <ChevronDown
                size={15}
                className={[
                  "text-[var(--aq-muted)] transition-transform",
                  profileMenuOpen
                    ? "rotate-180"
                    : "",
                ].join(" ")}
              />
            </button>
          </div>
        </div>
      </aside>

      <ThemeSettings
        open={settingsOpen}
        onClose={() =>
          setSettingsOpen(false)
        }
      />
    </>
  );
}
