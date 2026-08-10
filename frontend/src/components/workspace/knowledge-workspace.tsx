import {
  ChevronDown,
  Search,
} from "lucide-react";

import { RAGWorkspace } from "@/components/chat/rag-workspace";
import { DocumentPanel } from "@/components/documents/document-panel";
import type { UserResponse } from "@/types/auth";

type KnowledgeWorkspaceProps = {
  user: UserResponse;
};

export function KnowledgeWorkspace({
  user,
}: KnowledgeWorkspaceProps) {
  return (
    <div className="flex min-w-0 flex-1 flex-col bg-[var(--aq-bg)]">
      <header className="flex h-[72px] shrink-0 items-center border-b border-[var(--aq-border)] bg-[var(--aq-topbar)] px-8">
        <div className="flex h-10 w-[520px] items-center gap-3 rounded-xl border border-[var(--aq-border)] bg-[var(--aq-panel)] px-4">
          <Search
            size={16}
            className="text-[var(--aq-muted)]"
          />

          <input
            placeholder="Search chats, documents, sources..."
            className="min-w-0 flex-1 bg-transparent text-sm text-[var(--aq-text)] outline-none placeholder:text-[var(--aq-muted)]"
          />

          <span className="text-xs text-[var(--aq-muted)]">
            ⌘K
          </span>
        </div>

        <div className="ml-auto flex items-center gap-3">
          <button
            type="button"
            className="flex h-9 w-9 items-center justify-center rounded-full border border-[var(--aq-border)] bg-[var(--aq-panel)] text-sm"
          >
            ?
          </button>

          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--aq-blue)] text-xs font-semibold text-white">
            {user.username
              .slice(0, 1)
              .toUpperCase()}
          </div>

          <span className="max-w-[140px] truncate text-sm font-semibold">
            {user.username}
          </span>

          <ChevronDown
            size={15}
            className="text-[var(--aq-muted)]"
          />
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col px-6 pb-6 pt-5">
        <div className="mb-5">
          <h1 className="text-2xl font-bold tracking-tight">
            Knowledge Chat
          </h1>

          <p className="mt-1 text-sm text-[var(--aq-muted)]">
            Upload documents and ask grounded questions
            with traceable sources.
          </p>

          <div className="mt-3 flex gap-2">
            <span className="rounded-lg bg-[var(--aq-card)] px-3 py-1.5 text-[11px] font-semibold text-[var(--aq-success)]">
              ● Backend connected
            </span>

            <span className="rounded-lg bg-[var(--aq-card)] px-3 py-1.5 text-[11px] font-semibold text-[var(--aq-cyan)]">
              Private workspace
            </span>
          </div>
        </div>

        <div className="grid min-h-0 flex-1 grid-cols-[300px_minmax(520px,1fr)_320px] gap-4">
          <DocumentPanel />

          <RAGWorkspace />
        </div>
      </div>
    </div>
  );
}