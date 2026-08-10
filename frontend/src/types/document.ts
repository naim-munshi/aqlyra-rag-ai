export type DocumentStatus =
  | "uploaded"
  | "queued"
  | "processing"
  | "ready"
  | "failed";

export type DocumentResponse = {
  id: string;
  user_id: string;
  original_filename: string;
  content_type: string;
  file_extension: string;
  file_size: number;
  checksum_sha256: string;
  status: DocumentStatus;
  language: string | null;
  page_count: number | null;
  word_count: number | null;
  parsing_quality_score: number | null;
  requires_ocr: boolean;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  processed_at: string | null;
};

export type DocumentListResponse = {
  items: DocumentResponse[];
  total: number;
  limit: number;
  offset: number;
};

export type DocumentUnitType =
  | "page"
  | "slide"
  | "sheet"
  | "section"
  | "text";

export type DocumentUnitResponse = {
  id: string;
  document_id: string;
  unit_index: number;
  unit_type: DocumentUnitType;
  source_label: string;
  content: string;
  content_hash: string;
  char_count: number;
  word_count: number;
  unit_metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type DocumentUnitListResponse = {
  document_id: string;
  document_status: DocumentStatus;
  items: DocumentUnitResponse[];
  total: number;
  limit: number;
  offset: number;
};