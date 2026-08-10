import { RAGWorkspace } from "@/components/chat/rag-workspace";
import type { UserResponse } from "@/types/auth";

type KnowledgeWorkspaceProps = {
  user: UserResponse;
};

export function KnowledgeWorkspace({
  user,
}: KnowledgeWorkspaceProps) {
  return (
    <div
      aria-label={`${user.username}'s knowledge workspace`}
      className="flex min-w-0 flex-1 flex-col bg-[var(--aq-bg)]"
    >
      <header className="flex h-[64px] shrink-0 items-center border-b border-[var(--aq-border)] bg-[var(--aq-topbar)] px-6">
        <div>
          <h1 className="text-sm font-semibold">
            Knowledge Chat
          </h1>

          <p className="mt-0.5 text-[10px] text-[var(--aq-muted)]">
            Grounded answers from your documents
          </p>
        </div>
      </header>

      <main className="min-h-0 flex-1 p-4">
        <RAGWorkspace />
      </main>
    </div>
  );
}