"use client";

import { useState } from "react";
import { BookOpenCheck, ExternalLink, RefreshCw, ShieldCheck } from "lucide-react";

type StudyPanel = "overview" | "universities" | "research" | "documents";
type Brief = {
  case_id: string;
  generated_at: string;
  status: "planning_snapshot_unverified";
  summary: {
    shortlisted_programs: number;
    displayed_programs: number;
    programs_with_reported_gaps: number;
    unresolved_program_criteria: number;
    linked_ready_documents: number;
    outstanding_self_review_items: number;
    saved_research_topics: number;
    stale_research_topics: number;
  };
  documents: {
    ready_count: number;
    linked_categories: string[];
    outstanding_self_review: { key: string; title: string; state: string }[];
    note: string;
  };
  programs: {
    university_id: string;
    university_name: string;
    program: string;
    assessment: string;
    gap_count: number;
    unknown_count: number;
    needs_review: { criterion: string; status: string; detail: string }[];
    evidence_url: string | null;
    source_stale: boolean;
    provenance: string;
  }[];
  saved_source_links: {
    topic: string;
    citation: string;
    title: string;
    url: string;
    source_type: string;
    age_days: number;
    stale: boolean;
    verification_status: string;
  }[];
  next_actions: {
    id: string;
    title: string;
    reason: string;
    urgency: "urgent" | "next" | "later";
    research_topic: string | null;
  }[];
  privacy: {
    external_requests_made: number;
    document_text_accessed: boolean;
    document_excerpts_shared: boolean;
  };
  disclaimer: string;
};

export function StudyEvidenceBrief({
  caseId, onNavigate,
}: {
  caseId: string;
  onNavigate: (panel: StudyPanel) => void;
}) {
  const [brief, setBrief] = useState<Brief | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function checkReadiness() {
    if (loading) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(
        "/api/study-abroad/cases/" + encodeURIComponent(caseId) + "/evidence-brief",
        { cache: "no-store" },
      );
      if (!response.ok) {
        throw new Error(response.status === 503
          ? "Study evidence service is temporarily unavailable."
          : "Could not read this plan's saved evidence.");
      }
      const data = await response.json() as Brief;
      if (data.case_id !== caseId || data.status !== "planning_snapshot_unverified"
          || !data.summary || !Array.isArray(data.programs)
          || !Array.isArray(data.saved_source_links)) {
        throw new Error("Unexpected study evidence response.");
      }
      setBrief(data);
    } catch (cause) {
      setBrief(null);
      setError(cause instanceof Error ? cause.message : "Unable to check the saved evidence.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section aria-label="Study evidence readiness" className="rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-2.5">
          <BookOpenCheck aria-hidden="true" size={19} className="mt-0.5 shrink-0 text-[var(--aq-blue)]" />
          <div>
            <h2 className="text-base font-semibold">My Study Evidence Brief</h2>
            <p className="mt-1 max-w-xl text-xs leading-5 text-[var(--aq-muted)]">
              One check of your saved programs, eligibility gaps, dated research and private document readiness. No external search or file sharing.
            </p>
          </div>
        </div>
        <button type="button" disabled={loading}
          onClick={() => { void checkReadiness(); }}
          className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-[var(--aq-blue)] px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">
          <RefreshCw size={14} aria-hidden="true" className={loading ? "animate-spin" : ""} />
          {loading ? "Checking saved evidence…" : brief ? "Refresh brief" : "Check my readiness"}
        </button>
      </div>
      {error && <p role="alert" className="mt-3 text-xs text-red-400">{error}</p>}
      {brief && (
        <div className="mt-4 space-y-4" aria-live="polite">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {([
              ["Programs", brief.summary.shortlisted_programs],
              ["Programs with gaps", brief.summary.programs_with_reported_gaps],
              ["Ready linked files", brief.summary.linked_ready_documents],
              ["Old research topics", brief.summary.stale_research_topics],
            ] as const).map(([label, value]) => (
              <div key={label} className="rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] p-3">
                <span className="block text-[11px] text-[var(--aq-muted)]">{label}</span>
                <strong className="mt-1 block text-xl">{value}</strong>
              </div>
            ))}
          </div>
          <p className="text-xs text-[var(--aq-muted)]">
            {brief.summary.unresolved_program_criteria} unknown program criteria
            {" · "}{brief.summary.outstanding_self_review_items} checklist items awaiting your review
            {" · "}{brief.summary.saved_research_topics} saved research topics.
          </p>
          {brief.programs.length === 0 ? (
            <div className="rounded-xl border border-[var(--aq-border)] p-3 text-xs">
              No saved university programs yet. Your readiness cannot be assessed until you shortlist real programs.
              <button type="button" className="ml-2 text-[var(--aq-blue)] underline"
                onClick={() => onNavigate("universities")}>Explore programs</button>
            </div>
          ) : (
            <div>
              <h3 className="text-sm font-semibold">Program gaps to investigate</h3>
              <div className="mt-2 space-y-2">
                {brief.programs.slice(0, 4).map(program => (
                  <details key={program.university_id}
                    className="rounded-xl border border-[var(--aq-border)] p-3">
                    <summary className="cursor-pointer text-xs font-semibold">
                      {program.university_name} · {program.program}
                      <span className="ml-2 font-normal text-[var(--aq-muted)]">
                        {program.gap_count} reported gaps · {program.unknown_count} unknown
                      </span>
                    </summary>
                    <div className="mt-2 space-y-2 text-xs leading-5">
                      {program.needs_review.length ? program.needs_review.map(issue => (
                        <p key={issue.criterion}>
                          <strong>{issue.criterion}: </strong>{issue.detail}
                          <span className="ml-1 text-[var(--aq-muted)]">({issue.status.replaceAll("_", " ")})</span>
                        </p>
                      )) : <p className="text-[var(--aq-muted)]">All entered comparisons match; admission remains unverified.</p>}
                      {program.evidence_url && <a href={program.evidence_url} target="_blank" rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-[var(--aq-blue)]">
                        <ExternalLink size={13} aria-hidden="true" />
                        Saved university-domain source · {program.source_stale ? "outdated" : "unverified"}
                      </a>}
                      <p className="text-[11px] text-[var(--aq-muted)]">
                        Entered thresholds are not independently verified. Confirm the exact degree and intake on the university website.
                      </p>
                    </div>
                  </details>
                ))}
              </div>
              {brief.summary.displayed_programs > 4 && <p className="mt-2 text-[11px] text-[var(--aq-muted)]">
                Showing 4 of {brief.summary.displayed_programs} programs here.
              </p>}
              <button type="button" onClick={() => onNavigate("universities")}
                className="mt-2 text-xs font-medium text-[var(--aq-blue)] underline">
                Review full program comparisons
              </button>
            </div>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-[var(--aq-border)] p-3">
              <h3 className="text-sm font-semibold">Saved public evidence</h3>
              {brief.saved_source_links.length === 0 ? (
                <p className="mt-2 text-xs text-[var(--aq-muted)]">No cited links saved yet. Research a topic with permission first.</p>
              ) : (
                <div className="mt-2 space-y-2">
                  {brief.saved_source_links.slice(0, 3).map(source => (
                    <a key={source.topic + source.citation} href={source.url}
                      target="_blank" rel="noopener noreferrer"
                      className="block break-words text-xs text-[var(--aq-blue)] hover:underline">
                      <ExternalLink size={12} className="mr-1 inline" aria-hidden="true" />
                      {source.topic} {source.citation} · {source.title}
                      <span className="block text-[11px] text-[var(--aq-muted)]">
                        {source.age_days} days old · {source.stale ? "Recheck" : "Needs source review"}
                      </span>
                    </a>
                  ))}
                </div>
              )}
              <button type="button" onClick={() => onNavigate("research")}
                className="mt-3 text-xs text-[var(--aq-blue)] underline">Review research sources</button>
            </div>
            <div className="rounded-xl border border-[var(--aq-border)] p-3">
              <h3 className="text-sm font-semibold">Private file readiness</h3>
              <p className="mt-2 text-xs">{brief.documents.ready_count} linked, processed files</p>
              <p className="mt-1 text-[11px] text-[var(--aq-muted)]">
                Categories: {brief.documents.linked_categories.join(", ") || "none yet"}
              </p>
              <p className="mt-2 text-[11px] leading-5 text-[var(--aq-muted)]">
                File contents were not read or sent anywhere; processing and authenticity are separate checks.
              </p>
              <button type="button" onClick={() => onNavigate("documents")}
                className="mt-3 text-xs text-[var(--aq-blue)] underline">Review linked documents</button>
            </div>
          </div>
          {brief.next_actions.length > 0 && <div>
            <h3 className="text-sm font-semibold">Priority next steps</h3>
            <ol className="mt-2 space-y-1.5 text-xs">
              {brief.next_actions.slice(0, 3).map((action, index) => (
                <li key={action.id} className="rounded-lg border border-[var(--aq-border)] p-2.5">
                  <strong>{index + 1}. {action.title}</strong>
                  <p className="mt-1 text-[11px] leading-5 text-[var(--aq-muted)]">{action.reason}</p>
                </li>
              ))}
            </ol>
          </div>}
          <div className="flex items-start gap-2 text-[11px] leading-5 text-[var(--aq-muted)]">
            <ShieldCheck aria-hidden="true" size={15} className="mt-0.5 shrink-0" />
            <p>
              Private, case-scoped read-only report. No external provider call; no document excerpts transmitted.
              {" "}{brief.disclaimer}
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
