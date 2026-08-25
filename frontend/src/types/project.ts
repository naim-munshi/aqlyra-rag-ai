import type {
  ConversationMode,
} from "@/types/conversation";


export type ProjectResponse = {
  id: string;
  name: string;
  mode: ConversationMode;
  created_at: string;
  updated_at: string;
};
