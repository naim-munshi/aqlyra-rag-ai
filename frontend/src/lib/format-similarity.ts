/** A lexical-only source has no measured dense similarity. */
export function formatSimilarity(score: number | null): string {
  if (score === null) {
    return "Lexical only";
  }
  return Number.isFinite(score) ? score.toFixed(3) : "Unavailable";
}
