"use client";

import { Menu } from "lucide-react";

import { RAGWorkspace } from "@/components/chat/rag-workspace";
import type { UserResponse } from "@/types/auth";

type KnowledgeWorkspaceProps = {
  user: UserResponse;
  onOpenSidebar?: () => void;
};

export function KnowledgeWorkspace({
  user,
  onOpenSidebar,
}: KnowledgeWorkspaceProps) {
  return (
    <div
      aria-label={`${user.username}'s knowledge workspace`}
      className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-[var(--aq-bg)]"
    >
      <header className="flex h-14 shrink-0 items-center border-b border-[var(--aq-border)] bg-[var(--aq-topbar)] px-3 sm:px-4 md:h-[64px] md:px-6">
        <button
          type="button"
          aria-label="Open navigation"
          aria-controls="aqlyra-navigation-drawer"
          onClick={onOpenSidebar}
          className="mr-3 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] text-[var(--aq-text)] md:hidden"
        >
          <Menu size={20} />
        </button>
        <div className="min-w-0">
          <h1 className="text-sm font-semibold">
            Knowledge Chat
          </h1>

          <p className="mt-0.5 hidden text-[10px] text-[var(--aq-muted)] sm:block">
            Grounded answers from your documents
          </p>
        </div>
      </header>

      <main className="min-h-0 min-w-0 flex-1 p-2 sm:p-3 md:p-4">
        <RAGWorkspace
          userId={user.id}
        />
      </main>
    </div>
  );
}
