export type ChatToolId = "upload" | "web" | "browser" | "knowledge" | "documents";

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
      label: "Web Research",
      description: "Search live sources with citations",
      href: "/web",
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
