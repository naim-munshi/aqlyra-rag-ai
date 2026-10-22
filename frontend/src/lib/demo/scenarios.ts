/**
 * Public portfolio preview data. These are authored examples, NOT responses
 * from the Aqlyra API, user uploads, or retrieval infrastructure.
 */
export type PreviewMode = "knowledge" | "converse";

export type PreviewScenario = {
  id: string;
  mode: PreviewMode;
  title: string;
  prompt: string;
  answer: string;
  fileName: string | null;
  sourceHeading: string | null;
  sourceExcerpt: string | null;
  reasoningNote: string;
};

export const previewScenarios: readonly PreviewScenario[] = [
  {
    id: "access",
    mode: "knowledge",
    title: "Access control",
    prompt: "How does Aqlyra protect documents between users?",
    answer:
      "In the illustrative policy, access is scoped to the authenticated owner. " +
      "Document, conversation and memory requests are checked against that owner, " +
      "so knowing another user's record ID is not sufficient to read it. [S1]",
    fileName: "security_policy.md",
    sourceHeading: "Sample access policy",
    sourceExcerpt:
      "Every document and conversation belongs to an authenticated user. " +
      "Requests for another user's records must be rejected.",
    reasoningNote:
      "Evidence-backed answer with an explicit source reference.",
  },
  {
    id: "recovery",
    mode: "knowledge",
    title: "Disaster recovery",
    prompt: "What happens if the database needs to be restored?",
    answer:
      "The example recovery plan calls for a verified database backup and " +
      "matching upload archive. Recovery should first be rehearsed on a " +
      "disposable environment; restoring the live database may replace newer writes. [S1]",
    fileName: "continuity_plan.md",
    sourceHeading: "Sample recovery checklist",
    sourceExcerpt:
      "Verify database and upload archives, test restore against disposable " +
      "data, and plan for potential loss of writes after the last snapshot.",
    reasoningNote:
      "The response is tied to a specific, inspectable sample excerpt.",
  },
  {
    id: "privacy",
    mode: "knowledge",
    title: "Privacy controls",
    prompt: "What information should application logs avoid?",
    answer:
      "According to the illustrative privacy standard, operational logs " +
      "should not contain passwords, API credentials, or private document " +
      "contents. They should record only the minimum information needed " +
      "to diagnose requests and service failures. [S1]",
    fileName: "privacy_standard.md",
    sourceHeading: "Sample logging standard",
    sourceExcerpt:
      "Do not include authentication secrets or the contents of private " +
      "documents in operational logs. Log only necessary diagnostics.",
    reasoningNote:
      "The quoted evidence is an authored example, not a live retrieval.",
  },
  {
    id: "explain",
    mode: "converse",
    title: "Explain the system",
    prompt: "Explain hybrid search in simple terms.",
    answer:
      "Hybrid search combines two complementary strategies: semantic " +
      "search finds passages with similar meaning, while keyword search " +
      "matches explicit terms. Aqlyra's architecture merges these " +
      "candidate lists using Reciprocal Rank Fusion before choosing " +
      "evidence for a grounded answer.",
    fileName: null,
    sourceHeading: null,
    sourceExcerpt: null,
    reasoningNote:
      "Illustrative general-chat response; no model request was made.",
  },
  {
    id: "pipeline",
    mode: "converse",
    title: "Architecture walkthrough",
    prompt: "What does a RAG pipeline do after I upload a PDF?",
    answer:
      "A typical pipeline extracts the document text, splits it into " +
      "searchable chunks, generates embeddings, and stores searchable " +
      "records. A question then retrieves relevant chunks, builds context " +
      "for an LLM, and validates the generated answer's citations.",
    fileName: null,
    sourceHeading: null,
    sourceExcerpt: null,
    reasoningNote:
      "Architectural example only; no document has been processed here.",
  },
];

export function scenariosForMode(mode: PreviewMode): PreviewScenario[] {
  return previewScenarios.filter((scenario) => scenario.mode === mode);
}

export function findScenario(id: string): PreviewScenario | undefined {
  return previewScenarios.find((scenario) => scenario.id === id);
}
