import type { RAGAnswerResponse } from "@/types/rag";

export type AgentTraceStep = {
  id: string;
  step_index: number;
  step_type: string;
  tool_name: string | null;
  status: string;
  input_summary: Record<string, unknown>;
  output_summary: Record<string, unknown>;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  created_at: string;
};

export type AgentResearchResponse = RAGAnswerResponse & {
  trace_id: string;
  cost_usd: number;
  cost_basis: string;
  steps: AgentTraceStep[];
};

export type AgentRunSummary = {
  id: string;
  trace_id: string;
  question_redacted: string;
  status: string;
  provider_name: string | null;
  model_name: string | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  cost_basis: string;
  latency_ms: number;
  created_at: string;
};

export type AgentRunDetail = AgentRunSummary & {
  answer_redacted: string | null;
  steps: AgentTraceStep[];
};

export type AgentApiError = {
  detail?: string | { message?: string } | Array<{ msg?: string }>;
};
