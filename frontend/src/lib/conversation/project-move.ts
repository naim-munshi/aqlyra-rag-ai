import type { ConversationMode } from "@/types/conversation";
import type { ProjectResponse } from "@/types/project";

// Backend requires project.mode == conversation.mode (never silently change it).
export function projectsForConversation(
  projects: ProjectResponse[], mode: ConversationMode,
): ProjectResponse[] {
  return projects.filter((project) => project.mode === mode);
}
