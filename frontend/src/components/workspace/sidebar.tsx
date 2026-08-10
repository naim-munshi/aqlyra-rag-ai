"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  CircleHelp,
  FileText,
  FolderPlus,
  History,
  House,
  Library,
  LogOut,
  MessageSquareText,
  Plus,
  Search,
  Settings,
  Sparkles,
} from "lucide-react";

import { AqlyraLogo } from "@/components/brand/aqlyra-logo";
import { ThemeSettings } from "@/components/theme/theme-settings";
import type { UserResponse } from "@/types/auth";

type SidebarProps = {
  user: UserResponse;
};

const navigation = [
  {
    label: "Home",
    icon: House,
  },
  {
    label: "Documents",
    icon: FileText,
  },
  {
    label: "Collections",
    icon: Library,
  },
  {
    label: "RAG Chat",
    icon: MessageSquareText,
    active: true,
  },
  {
    label: "Retrieval",
    icon: Search,
  },
  {
    label: "History",
    icon: History,
  },
];

export function Sidebar({
  user,
}: SidebarProps) {
  const router = useRouter();

  const [settingsOpen, setSettingsOpen] =
    useState(false);

  async function handleLogout() {
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
            className="flex h-11 w-full items-center gap-3 rounded-xl border border-[var(--aq-cyan)] bg-[var(--aq-card)] px-4 text-sm font-semibold text-[var(--aq-text)] transition hover:bg-[var(--aq-control)]"
          >
            <FolderPlus
              size={18}
              strokeWidth={1.8}
            />

            <span>New project</span>
          </button>

          <button
            type="button"
            className="flex h-11 w-full items-center gap-3 rounded-xl bg-[var(--aq-blue)] px-4 text-sm font-semibold text-white transition hover:bg-[var(--aq-blue-hover)]"
          >
            <Plus
              size={18}
              strokeWidth={2}
            />

            <span>New chat</span>
          </button>
        </div>

        <nav className="mt-5 space-y-1">
          {navigation.map((item) => {
            const Icon = item.icon;

            return (
              <button
                key={item.label}
                type="button"
                className={[
                  "flex h-11 w-full items-center gap-3 rounded-xl px-3 text-sm transition",
                  item.active
                    ? "bg-[var(--aq-blue-muted)] font-semibold text-[var(--aq-text)]"
                    : "text-[var(--aq-muted)] hover:bg-[var(--aq-card)] hover:text-[var(--aq-text)]",
                ].join(" ")}
              >
                <span
                  className={[
                    "flex h-8 w-8 items-center justify-center rounded-full border",
                    item.active
                      ? "border-[var(--aq-blue)] bg-[var(--aq-blue)] text-white"
                      : "border-[var(--aq-border)] bg-[var(--aq-panel)] text-[var(--aq-muted)]",
                  ].join(" ")}
                >
                  <Icon
                    size={15}
                    strokeWidth={1.8}
                  />
                </span>

                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="mt-auto">
          <div className="rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-4">
            <div className="flex items-center gap-2">
              <Sparkles
                size={16}
                className="text-[var(--aq-cyan)]"
              />

              <p className="text-sm font-bold text-[var(--aq-text)]">
                Aqlyra Plus
              </p>
            </div>

            <p className="mt-3 text-xs leading-5 text-[var(--aq-muted)]">
              More storage, higher limits,
              advanced voice and team tools.
            </p>

            <button
              type="button"
              className="mt-4 h-10 w-full rounded-xl bg-[var(--aq-blue)] text-xs font-semibold text-white transition hover:bg-[var(--aq-blue-hover)]"
            >
              Upgrade
            </button>
          </div>

          <div className="mt-5 rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] p-3">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--aq-blue)] text-xs font-bold text-white">
                {user.username
                  .slice(0, 1)
                  .toUpperCase()}
              </div>

              <div className="min-w-0">
                <p className="truncate text-xs font-semibold text-[var(--aq-text)]">
                  {user.username}
                </p>

                <p className="mt-1 truncate text-[10px] text-[var(--aq-muted)]">
                  {user.email}
                </p>
              </div>
            </div>
          </div>

          <div className="mt-4 flex items-center justify-between px-2">
            <button
              type="button"
              onClick={() =>
                setSettingsOpen(true)
              }
              className="flex items-center gap-2 text-xs text-[var(--aq-muted)] transition hover:text-[var(--aq-text)]"
            >
              <Settings size={15} />
              Settings
            </button>

            <button
              type="button"
              className="flex items-center gap-2 text-xs text-[var(--aq-muted)] transition hover:text-[var(--aq-text)]"
            >
              <CircleHelp size={15} />
              Help
            </button>
          </div>

          <button
            type="button"
            onClick={handleLogout}
            className="mt-4 flex h-10 w-full items-center justify-center gap-2 rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] text-xs font-semibold text-[var(--aq-muted)] transition hover:bg-[var(--aq-control)] hover:text-[var(--aq-text)]"
          >
            <LogOut size={15} />
            Sign out
          </button>
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