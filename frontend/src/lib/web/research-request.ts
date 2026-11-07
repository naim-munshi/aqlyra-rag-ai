export const RESEARCH_MODES = [
  "search", "deep", "compare", "fact_check", "url",
] as const;

export type ResearchMode = (typeof RESEARCH_MODES)[number];

export type ResearchRequest = {
  question: string;
  max_sources: number;
  mode: ResearchMode;
  source_url?: string;
  time_range?: "day" | "week" | "month" | "year";
  include_domains?: string[];
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

  const timeRange = body.time_range;
  if (
    timeRange !== undefined &&
    !["day", "week", "month", "year"].includes(String(timeRange))
  ) return null;
  const rawDomains = body.include_domains === undefined ? [] : body.include_domains;
  if (!Array.isArray(rawDomains) || rawDomains.length > 3) return null;
  const domainPattern = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$/;
  const domains: string[] = [];
  for (const entry of rawDomains) {
    if (typeof entry !== "string") return null;
    const domain = entry.trim().toLowerCase().replace(/\.$/, "");
    if (!domainPattern.test(domain) || domain.length > 253 ||
        /\.(local|localhost|internal|test|invalid)$/.test(domain) ||
        /^\d+\.\d+\.\d+\.\d+$/.test(domain) ||
        domains.includes(domain)) return null;
    domains.push(domain);
  }
  if (mode === "url" && (timeRange !== undefined || domains.length > 0)) return null;
  const filters = {
    ...(timeRange ? { time_range: timeRange as ResearchRequest["time_range"] } : {}),
    ...(domains.length ? { include_domains: domains } : {}),
  };

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
  return { question, max_sources: maxSources, mode: mode as ResearchMode, ...filters };
}
