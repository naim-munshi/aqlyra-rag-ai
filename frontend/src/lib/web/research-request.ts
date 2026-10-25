export const RESEARCH_MODES = [
  "search", "deep", "compare", "fact_check", "url",
] as const;

export type ResearchMode = (typeof RESEARCH_MODES)[number];

export type ResearchRequest = {
  question: string;
  max_sources: number;
  mode: ResearchMode;
  source_url?: string;
};

export function parseResearchRequest(value: unknown): ResearchRequest | null {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const body = value as Record<string, unknown>;
  if (typeof body.question !== "string") return null;
  const question = body.question.trim();
  if (question.length < 3 || question.length > 600) return null;
  const mode = body.mode === undefined ? "search" : body.mode;
  if (!RESEARCH_MODES.some((item) => item === mode)) return null;
  const maxSources = body.max_sources === undefined ? 4 : body.max_sources;
  if (
    typeof maxSources !== "number" ||
    !Number.isInteger(maxSources) ||
    maxSources < 1 || maxSources > 5
  ) {
    return null;
  }
  if (mode === "url") {
    if (typeof body.source_url !== "string") return null;
    const sourceUrl = body.source_url.trim();
    if (sourceUrl.length === 0 || sourceUrl.length > 2048) return null;
    try {
      const parsed = new URL(sourceUrl);
      if (parsed.protocol !== "https:" || !parsed.hostname) return null;
    } catch {
      return null;
    }
    return {
      question,
      max_sources: maxSources,
      mode,
      source_url: sourceUrl,
    };
  }
  if (body.source_url !== undefined) return null;
  return { question, max_sources: maxSources, mode: mode as ResearchMode };
}
