export type ChunkRole =
  | "content"
  | "summary"
  | "proposition";

export type RAGAnswerRequest = {
  question: string;
  top_k?: number;
  document_ids?: string[];
  chunk_roles?: ChunkRole[];
  min_similarity?: number | null;
  max_context_tokens?: number;
  max_source_tokens?: number;
  max_sources?: number;
};

export type RAGCitationResponse = {
  source_id: string;
  chunk_id: string;
  document_id: string;
  parent_chunk_id: string | null;

  filename: string;

  chunk_role: ChunkRole;
  chunk_level: number;
  chunk_index: number;

  source_label: string;
  section_path: string[];

  start_page: number | null;
  end_page: number | null;

  similarity_score: number;

  excerpt: string;
  was_truncated: boolean;
};

export type RAGUsageResponse = {
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  evidence_tokens: number;
};

export type RAGAnswerResponse = {
  question: string;
  answer: string;

  is_refusal: boolean;

  provider_name: string;
  model_name: string;
  response_id: string | null;

  citations: RAGCitationResponse[];
  citation_count: number;

  retrieved_count: number;
  context_source_count: number;
  skipped_evidence_count: number;
  evidence_was_truncated: boolean;

  usage: RAGUsageResponse;
};

export type RAGErrorResponse = {
  detail?:
    | string
    | Array<{
        type?: string;
        loc?: Array<string | number>;
        msg?: string;
        input?: unknown;
      }>;
};