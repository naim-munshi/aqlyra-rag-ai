"use client";

import { useEffect, useState } from "react";

import { KnowledgeWorkspace } from "@/components/workspace/knowledge-workspace";
import { Sidebar } from "@/components/workspace/sidebar";
import type { UserResponse } from "@/types/auth";

type Props = { user: UserResponse };

/** A single sidebar, docked on desktop and a dismissible drawer on phones. */
export function ResponsiveWorkspaceShell({ user }: Props) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (!sidebarOpen) return;

    const priorOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    function closeSidebar() { setSidebarOpen(false); }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") closeSidebar();
    }

    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("aqlyra:new-chat", closeSidebar);
    window.addEventListener("aqlyra:open-conversation", closeSidebar);
    window.addEventListener("aqlyra:open-documents", closeSidebar);
    window.addEventListener("aqlyra:focus-chat", closeSidebar);

    return () => {
      document.body.style.overflow = priorOverflow;
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("aqlyra:new-chat", closeSidebar);
      window.removeEventListener("aqlyra:open-conversation", closeSidebar);
      window.removeEventListener("aqlyra:open-documents", closeSidebar);
      window.removeEventListener("aqlyra:focus-chat", closeSidebar);
    };
  }, [sidebarOpen]);

  return (
    <main className="flex h-screen h-dvh min-w-0 overflow-hidden bg-[var(--aq-bg)] text-[var(--aq-text)]">
      {sidebarOpen && (
        <button
          type="button"
          aria-label="Close navigation drawer"
          className="fixed inset-0 z-40 bg-black/65 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <div
        id="aqlyra-navigation-drawer"
        className={[
          "fixed inset-y-0 left-0 z-50 h-full w-[min(84vw,300px)] max-w-full transform border-r border-[var(--aq-border)] bg-[var(--aq-bg-deep)] transition-transform duration-200",
          "md:static md:z-auto md:w-[244px] md:shrink-0 md:transform-none md:border-0 md:transition-none",
          sidebarOpen
            ? "visible translate-x-0"
            : "invisible -translate-x-full md:visible md:translate-x-0",
        ].join(" ")}
      >
        <Sidebar user={user} />
      </div>

      <KnowledgeWorkspace user={user} onOpenSidebar={() => setSidebarOpen(true)} />
    </main>
  );
}
