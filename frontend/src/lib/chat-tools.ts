export type ChatToolId = "upload" | "web" | "web-deep" | "web-off" | "browser" | "knowledge" | "documents";

export type ChatTool = {
  id: ChatToolId;
  label: string;
  description: string;
  href?: string;
};

export function getChatTools(mode: "normal" | "knowledge"): ChatTool[] {
  return [
    {
      id: "upload",
      label: "Upload file",
      description: "Attach a document or image to your chat",
    },
    {
      id: "web",
      label: "Search the web",
      description: "Search public sources in this chat without opening another page",
    },
    {
      id: "web-deep",
      label: "Deep research",
      description: "Investigate multiple public sources in this chat",
    },
    {
      id: "web-off",
      label: "Don't search web",
      description: "Answer from the AI without searching the public web",
    },
    {
      id: "browser",
      label: "Browser Agent",
      description: "Review and approve a read-only browser task",
      href: "/agent/browser",
    },
    {
      id: "knowledge",
      label: mode === "knowledge" ? "Switch to Converse" : "Knowledge chat",
      description: mode === "knowledge"
        ? "Return to general AI conversation"
        : "Ask questions grounded in your documents",
    },
    {
      id: "documents",
      label: "My documents",
      description: "Browse your existing private knowledge files",
    },
  ];
}

export type ChatToolsMenuPosition = {
  left: number;
  bottom: number;
  width: number;
  maxHeight: number;
};

/**
 * Put the popup above the + trigger, with an explicit fixed width.
 * Fixed positioning + a body portal prevents the chat's overflow-hidden
 * panels from clipping or shrinking the menu.
 */
export function getChatToolsMenuPosition(
  anchor: { left: number; top: number },
  viewportWidth: number,
  viewportHeight: number,
): ChatToolsMenuPosition {
  const inset = 12;
  const width = Math.max(0, Math.min(280, viewportWidth - inset * 2));
  const left = Math.max(
    inset,
    Math.min(anchor.left, viewportWidth - inset - width),
  );
  return {
    left,
    width,
    bottom: Math.max(0, viewportHeight - anchor.top + 10),
    maxHeight: Math.max(64, Math.min(320, anchor.top - 22)),
  };
}
