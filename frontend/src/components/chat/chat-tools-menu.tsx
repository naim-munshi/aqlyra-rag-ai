"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";
import {
  FileUp, Files, Globe2, MousePointer2,
  Plus, BookOpen, MessageSquareText, GraduationCap, X,
} from "lucide-react";

import {
  getChatTools,
  getChatToolsMenuPosition,
  type ChatToolId,
  type ChatToolsMenuPosition,
} from "@/lib/chat-tools";

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
  study: GraduationCap,
} as const;

export function ChatToolsMenu({
  mode, disabled, onUpload, onOpenDocuments, onSwitchMode,
}: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<ChatToolsMenuPosition | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const tools = getChatTools(mode);

  const updatePosition = useCallback(() => {
    const trigger = triggerRef.current;
    if (!trigger) return;
    const rect = trigger.getBoundingClientRect();
    setPosition(getChatToolsMenuPosition(
      rect,
      window.innerWidth,
      window.innerHeight,
    ));
  }, []);

  function toggleMenu() {
    if (open) {
      setOpen(false);
      return;
    }
    updatePosition();
    setOpen(true);
  }

  useEffect(() => {
    if (!open) return;

    const frame = window.requestAnimationFrame(() => {
      menuRef.current?.querySelector<HTMLButtonElement>(
        'button[role="menuitem"]:not([disabled])',
      )?.focus();
    });

    function isInside(target: EventTarget | null) {
      return target instanceof Node && (
        triggerRef.current?.contains(target) ||
        menuRef.current?.contains(target)
      );
    }
    function handlePointerDown(event: PointerEvent) {
      if (!isInside(event.target)) setOpen(false);
    }
    function handleFocus(event: FocusEvent) {
      if (!isInside(event.target)) setOpen(false);
    }
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        triggerRef.current?.focus();
        return;
      }
      if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;

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
      buttons[next]?.focus();
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("focusin", handleFocus);
    document.addEventListener("keydown", handleKey);
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);

    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("focusin", handleFocus);
      document.removeEventListener("keydown", handleKey);
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [open, updatePosition]);

  function selectTool(id: ChatToolId, href?: string) {
    setOpen(false);
    if (id === "upload") {
      // Keep Safari's native file picker inside the actual click handler.
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
    <>
      <button
        ref={triggerRef}
        type="button"
        title="Add files or use Aqlyra tools"
        aria-label="Add files or use Aqlyra tools"
        aria-haspopup="menu"
        aria-controls={open ? menuId : undefined}
        aria-expanded={open}
        disabled={disabled}
        onClick={toggleMenu}
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-[var(--aq-border)] bg-[var(--aq-control)] text-[var(--aq-text)] transition hover:border-[var(--aq-blue)] hover:text-[var(--aq-blue)] focus-visible:outline-2 focus-visible:outline-[var(--aq-blue)] disabled:cursor-not-allowed disabled:opacity-50"
      >
        {open ? <X size={18} /> : <Plus size={20} />}
      </button>

      {open && position && createPortal(
        <div
          ref={menuRef}
          id={menuId}
          role="menu"
          aria-label="Aqlyra chat tools"
          style={{
            position: "fixed",
            left: position.left,
            bottom: position.bottom,
            width: position.width,
            maxHeight: position.maxHeight,
          }}
          className="aq-scrollbar z-[9999] overflow-y-auto rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-2 shadow-2xl"
        >
          <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--aq-muted)]">
            Tools
          </p>
          {tools.map((tool) => {
            const Icon = tool.id === "knowledge" && mode === "knowledge"
              ? MessageSquareText
              : icons[tool.id];
            return (
              <button
                key={tool.id}
                type="button"
                role="menuitem"
                title={tool.description}
                aria-label={tool.label + ". " + tool.description}
                onClick={() => selectTool(tool.id, tool.href)}
                className="flex h-11 w-full items-center gap-3 rounded-xl px-3 text-left transition hover:bg-[var(--aq-card)] focus-visible:bg-[var(--aq-card)] focus-visible:outline-2 focus-visible:outline-[var(--aq-blue)]"
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--aq-blue-soft)] text-[var(--aq-blue)]">
                  <Icon size={16} />
                </span>
                <span className="min-w-0 flex-1 truncate whitespace-nowrap text-[13px] font-medium text-[var(--aq-text)]">
                  {tool.label}
                </span>
              </button>
            );
          })}
        </div>,
        document.body,
      )}
    </>
  );
}
