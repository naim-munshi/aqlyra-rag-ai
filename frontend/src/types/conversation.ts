import type {
  DocumentResponse,
} from "@/types/document";

import type {
  RAGCitationResponse,
} from "@/types/rag";

export type ConversationMode =
  | "normal"
  | "knowledge";

export type ConversationResponse = {
  id: string;
  title: string;
  mode: ConversationMode;
  is_pinned: boolean;
  project_id: string | null;
  created_at: string;
  updated_at: string;
};

export type MessageAttachmentResponse = {
  id: string;
  document_id: string;
  position: number;
  document: DocumentResponse;
  created_at: string;
};

export type ConversationMessageResponse = {
  id: string;
  conversation_id: string;

  role:
    | "user"
    | "assistant";

  mode: ConversationMode;

  content: string;

  provider_name: string | null;
  model_name: string | null;
  response_id: string | null;

  citations: RAGCitationResponse[];

  is_refusal: boolean;

  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  evidence_tokens: number | null;

  attachments:
    MessageAttachmentResponse[];

  created_at: string;
};

export type ChatTurnResponse = {
  conversation_id: string;
  mode: ConversationMode;
  user_message: ConversationMessageResponse;
  assistant_message: ConversationMessageResponse;
};
