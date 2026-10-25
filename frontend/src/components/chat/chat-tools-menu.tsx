"use client";

import { useEffect, useId, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  FileUp, Files, Globe2, MousePointer2,
  Plus, BookOpen, MessageSquareText, X,
} from "lucide-react";

import { getChatTools, type ChatToolId } from "@/lib/chat-tools";

type Props = {
  mode: "normal" | "knowledge";
  disabled: boolean;
  onUpload: () => void;
  onOpenDocuments: () => void;
  onSwitchMode: () => void;
};

const icons = {
  upload: FileUp,
  web: Globe2,
  browser: MousePointer2,
  knowledge: BookOpen,
  documents: Files,
} as const;

export function ChatToolsMenu({
  mode, disabled, onUpload, onOpenDocuments, onSwitchMode,
}: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const tools = getChatTools(mode);

  useEffect(() => {
    if (!open) return;
    const frame = window.requestAnimationFrame(() => {
      menuRef.current?.querySelector<HTMLButtonElement>(
        'button[role="menuitem"]:not([disabled])',
      )?.focus();
    });

    function handlePointerDown(event: PointerEvent) {
      if (event.target instanceof Node &&
          !containerRef.current?.contains(event.target)) {
        setOpen(false);
      }
    }
    function handleFocus(event: FocusEvent) {
      if (event.target instanceof Node &&
          !containerRef.current?.contains(event.target)) {
        setOpen(false);
      }
    }
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        triggerRef.current?.focus();
      }
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp" &&
          event.key !== "Home" && event.key !== "End") return;

      const buttons = Array.from(
        menuRef.current?.querySelectorAll<HTMLButtonElement>(
          'button[role="menuitem"]:not([disabled])',
        ) ?? [],
      );
      if (!buttons.length) return;
      const current = buttons.indexOf(document.activeElement as HTMLButtonElement);
      let next = current;
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = buttons.length - 1;
      if (event.key === "ArrowDown") next = (current + 1) % buttons.length;
      if (event.key === "ArrowUp") next = (current + buttons.length - 1) % buttons.length;
      event.preventDefault();
      buttons[next].focus();
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("focusin", handleFocus);
    document.addEventListener("keydown", handleKey);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("focusin", handleFocus);
      document.removeEventListener("keydown", handleKey);
    };
  }, [open]);

  function selectTool(id: ChatToolId, href?: string) {
    setOpen(false);
    if (id === "upload") {
      // Must happen inside this click event for Safari's native file picker.
      onUpload();
    } else if (id === "documents") {
      onOpenDocuments();
    } else if (id === "knowledge") {
      onSwitchMode();
    } else if (href) {
      router.push(href);
    }
  }

  return (
    <div ref={containerRef} className="relative shrink-0">
      <button
        ref={triggerRef}
        type="button"
        title="Add files or use Aqlyra tools"
        aria-label="Add files or use Aqlyra tools"
        aria-haspopup="menu"
        aria-controls={open ? menuId : undefined}
        aria-expanded={open}
        disabled={disabled}
        onClick={() => setOpen(value => !value)}
        className="flex h-9 w-9 items-center justify-center rounded-full border border-[var(--aq-border)] bg-[var(--aq-control)] text-[var(--aq-text)] transition hover:border-[var(--aq-blue)] hover:text-[var(--aq-blue)] focus-visible:outline-2 focus-visible:outline-[var(--aq-blue)] disabled:cursor-not-allowed disabled:opacity-50"
      >
        {open ? <X size={18} /> : <Plus size={20} />}
      </button>
      {open && (
        <div
          ref={menuRef}
          id={menuId}
          role="menu"
          aria-label="Aqlyra chat tools"
          className="aq-scrollbar absolute bottom-full left-0 z-[80] mb-3 max-h-[min(70dvh,440px)] w-[min(85vw,325px)] overflow-y-auto rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-2 shadow-2xl"
        >
          <p className="px-3 pb-2 pt-2 text-[10px] font-bold uppercase tracking-wider text-[var(--aq-muted)]">
            Attach and use tools
          </p>
          {tools.map((tool, index) => {
            const Icon = tool.id === "knowledge" && mode === "knowledge"
              ? MessageSquareText
              : icons[tool.id];
            return (
              <div key={tool.id}>
                {index === 1 && <div className="my-2 border-t border-[var(--aq-border)]" />}
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => selectTool(tool.id, tool.href)}
                  className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition hover:bg-[var(--aq-card)] focus-visible:bg-[var(--aq-card)] focus-visible:outline-2 focus-visible:outline-[var(--aq-blue)]"
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--aq-blue-soft)] text-[var(--aq-blue)]">
                    <Icon size={17} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-xs font-semibold text-[var(--aq-text)]">{tool.label}</span>
                    <span className="mt-0.5 block text-[11px] leading-4 text-[var(--aq-muted)]">
                      {tool.description}
                    </span>
                  </span>
                </button>
              </div>
            );
          })}
          <p className="px-3 pb-1 pt-2 text-[10px] leading-4 text-[var(--aq-muted)]">
            Browser Agent opens its approval screen before it can run.
          </p>
        </div>
      )}
    </div>
  );
}
