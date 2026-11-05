"use client";

import { useEffect, useState, type FormEvent } from "react";
import { ExternalLink, RefreshCw, Scale, ShieldCheck } from "lucide-react";
import { StudyApplicationPacket } from "@/components/study-abroad/application-packet";

type Language = { test: "IELTS" | "TOEFL_iBT" | "Duolingo" | "JLPT"; score?: number; level?: string };
type Applicant = {
  gpa?: number; gpa_scale?: 4 | 5 | 10 | 100;
  annual_budget?: number; currency?: string;
  language?: Language; transfer_requested: boolean; completed_credits?: number;
};
type Requirements = {
  minimum_gpa?: number; gpa_scale?: 4 | 5 | 10 | 100;
  minimum_language?: Language; annual_tuition?: number; currency?: string;
  transfer_policy: "unknown" | "yes" | "no";
  evidence_report_id?: string; evidence_citation?: string;
};
type StudySchool = {
  id: string; name: string; program: string; program_url: string;
  requirements: Partial<Requirements>;
};
type SavedReport = {
  id: string; topic: string; searched_at: string;
  sources: { citation: string; title: string; url: string }[];
};
type Candidate = { title: string; url: string; citation: string; status: string };
type Comparison = {
  university_id: string; university_name: string; program: string;
  assessment: "potential_match_unverified" | "possible_gaps" | "insufficient_evidence";
  matched_count: number; gap_count: number; unknown_count: number;
  provenance: string; evidence_url: string | null; source_stale: boolean;
  criteria: { criterion: string; status: "reported_match" | "reported_gap" | "unknown"; detail: string }[];
};
type ExtractedDraft = {
  report_id: string; citation: string; source_url: string; stale: boolean;
  suggested_facts: Partial<Requirements>; status: string; note: string;
};
type ComparisonResponse = {
  profile: Applicant; programs: Comparison[]; disclaimer: string;
};

const currencyChoices = ["JPY", "USD", "EUR", "GBP", "AUD", "CAD", "BDT"];
const testChoices = ["", "IELTS", "TOEFL_iBT", "Duolingo", "JLPT"];
const fieldClass = "min-w-0 w-full rounded-lg border border-[var(--aq-border)] bg-[var(--aq-card)] px-3 py-2 text-sm outline-none";
const buttonClass = "min-h-10 rounded-lg border border-[var(--aq-blue)] px-4 py-2 text-xs font-semibold text-[var(--aq-blue)] disabled:opacity-40";
const cleanNumber = (v: string): number | undefined => v.trim() === "" ? undefined : Number(v);

async function api<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch("/api/study-abroad/" + path, {
    method, cache: "no-store",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const problem = await response.json().catch(() => null) as { detail?: unknown } | null;
    throw new Error(typeof problem?.detail === "string" ? problem.detail
      : "Program matching request failed (" + response.status + ")");
  }
  return await response.json() as T;
}

function relevantSource(programUrl: string, sourceUrl: string): boolean {
  try {
    const a = new URL(programUrl);
    const b = new URL(sourceUrl);
    const x = a.hostname.toLowerCase(), y = b.hostname.toLowerCase();
    return a.protocol === "https:" && b.protocol === "https:" &&
      (x === y || x.endsWith("." + y) || y.endsWith("." + x));
  } catch { return false; }
}

export function StudyFitWorkbench({
  caseId, revision, researchAllowed, onResearch, onUseCandidate, onEvidenceUpdated,
}: {
  caseId: string;
  revision: number;
  researchAllowed: boolean;
  onResearch: () => void;
  onUseCandidate: (url: string) => void;
  onEvidenceUpdated: () => void;
}) {
  const [matches, setMatches] = useState<ComparisonResponse | null>(null);
  const [schools, setSchools] = useState<StudySchool[]>([]);
  const [reports, setReports] = useState<SavedReport[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [suggestions, setSuggestions] = useState<ExtractedDraft[]>([]);
  const [evidenceTopic, setEvidenceTopic] = useState("admissions");
  const [selected, setSelected] = useState("");
  const [profile, setProfile] = useState({
    gpa: "", gpa_scale: "4", annual_budget: "", currency: "JPY",
    test: "", score: "", level: "N2",
    transfer_requested: false, completed_credits: "",
  });
  const [requirement, setRequirement] = useState({
    minimum_gpa: "", gpa_scale: "4", annual_tuition: "", currency: "JPY",
    test: "", score: "", level: "N2", transfer_policy: "unknown",
    source: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const target = "cases/" + encodeURIComponent(caseId);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    void Promise.all([
      api<ComparisonResponse>(target + "/matches"),
      api<StudySchool[]>(target + "/universities"),
      api<SavedReport[]>(target + "/research"),
      api<Candidate[]>(target + "/program-candidates"),
    ]).then(([comparison, programs, found, suggestions]) => {
      if (!alive) return;
      setMatches(comparison);
      setSchools(programs);
      setReports(found);
      setCandidates(suggestions);
      const p = comparison.profile;
      setProfile({
        gpa: p.gpa?.toString() ?? "",
        gpa_scale: p.gpa_scale?.toString() ?? "4",
        annual_budget: p.annual_budget?.toString() ?? "",
        currency: p.currency ?? "JPY",
        test: p.language?.test ?? "",
        score: p.language?.score?.toString() ?? "",
        level: p.language?.level ?? "N2",
        transfer_requested: p.transfer_requested ?? false,
        completed_credits: p.completed_credits?.toString() ?? "",
      });
      setSelected(old => programs.some(v => v.id === old) ? old : programs[0]?.id ?? "");
    }).catch(e => { if (alive) setError(String(e)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [caseId, revision, target]);

  useEffect(() => {
    const item = schools.find(s => s.id === selected);
    const req = item?.requirements ?? {};
    setRequirement({
      minimum_gpa: req.minimum_gpa?.toString() ?? "",
      gpa_scale: req.gpa_scale?.toString() ?? "4",
      annual_tuition: req.annual_tuition?.toString() ?? "",
      currency: req.currency ?? "JPY",
      test: req.minimum_language?.test ?? "",
      score: req.minimum_language?.score?.toString() ?? "",
      level: req.minimum_language?.level ?? "N2",
      transfer_policy: req.transfer_policy ?? "unknown",
      source: req.evidence_report_id && req.evidence_citation
        ? req.evidence_report_id + "|" + req.evidence_citation : "",
    });
  }, [schools, selected]);

  const selectedSchool = schools.find(item => item.id === selected);
  const evidence = reports.flatMap(report => (
    (report.topic === "universities" || report.topic === "admissions" ||
      report.topic === "transfer" || report.topic === "language" || report.topic === "costs")
      ? report.sources.filter(source => selectedSchool &&
          relevantSource(selectedSchool.program_url, source.url)).map(source => ({
            value: report.id + "|" + source.citation,
            label: source.title + " " + source.citation,
          }))
      : []
  ));

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError(""); setNotice("");
    try {
      const language = profile.test === "" ? undefined : profile.test === "JLPT"
        ? { test: "JLPT", level: profile.level }
        : { test: profile.test, score: cleanNumber(profile.score) };
      const body = {
        ...(profile.gpa.trim() === "" ? {} : {
          gpa: cleanNumber(profile.gpa), gpa_scale: Number(profile.gpa_scale),
        }),
        ...(profile.annual_budget.trim() === "" ? {} : {
          annual_budget: cleanNumber(profile.annual_budget), currency: profile.currency,
        }),
        ...(language ? { language } : {}),
        transfer_requested: profile.transfer_requested,
        ...(profile.completed_credits.trim() === "" ? {} : {
          completed_credits: cleanNumber(profile.completed_credits),
        }),
      };
      await api(target + "/applicant-facts", "PATCH", body);
      setMatches(await api<ComparisonResponse>(target + "/matches"));
      setNotice("Applicant facts saved. Program comparisons recalculated from your data.");
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }


  async function refreshOfficialSources() {
    if (!selected || !researchAllowed) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await api<{
        report: SavedReport;
        suggestions: ExtractedDraft[];
        verification_status: string;
        disclaimer: string;
      }>(
        target + "/universities/" + encodeURIComponent(selected) + "/refresh-evidence",
        "POST", { topic: evidenceTopic, confirm_share_program: true },
      );
      setReports(previous => [result.report, ...previous]);
      setSuggestions(result.suggestions);
      setNotice(result.suggestions.length > 0
        ? "Real university-domain research completed and draft thresholds extracted. Review the source and each criterion before saving."
        : "University-domain research saved with citations; no explicit thresholds were found. Check the original source.");
      // The advisor's saved research freshness should now refresh too.
      onEvidenceUpdated();
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  async function loadEvidenceDrafts() {
    if (!selected) return;
    setBusy(true); setError("");
    try {
      const data = await api<ExtractedDraft[]>(
        target + "/universities/" + encodeURIComponent(selected) + "/requirement-suggestions",
      );
      setSuggestions(data);
      setNotice(data.length === 0
        ? "No explicit GPA, language or tuition thresholds detected in saved first-party excerpts. Research the program and enter only facts you can confirm."
        : "Source-based draft values found. Open the official pages and review before using any criterion.");
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  function reviewSuggestion(draft: ExtractedDraft) {
    const fact = draft.suggested_facts;
    setRequirement(prev => ({
      ...prev,
      minimum_gpa: fact.minimum_gpa?.toString() ?? prev.minimum_gpa,
      gpa_scale: fact.gpa_scale?.toString() ?? prev.gpa_scale,
      annual_tuition: fact.annual_tuition?.toString() ?? prev.annual_tuition,
      currency: fact.currency ?? prev.currency,
      test: fact.minimum_language?.test ?? prev.test,
      score: fact.minimum_language?.score?.toString() ?? prev.score,
      level: fact.minimum_language?.level ?? prev.level,
      source: draft.report_id + "|" + draft.citation,
    }));
    setNotice("Draft values placed in the editable form. Confirm the full university page and click Save criteria to persist.");
  }

  async function saveRequirements(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const language = requirement.test === "" ? undefined : requirement.test === "JLPT"
        ? { test: "JLPT", level: requirement.level }
        : { test: requirement.test, score: cleanNumber(requirement.score) };
      const parts = requirement.source.split("|");
      const body = {
        ...(requirement.minimum_gpa.trim() === "" ? {} : {
          minimum_gpa: cleanNumber(requirement.minimum_gpa),
          gpa_scale: Number(requirement.gpa_scale),
        }),
        ...(requirement.annual_tuition.trim() === "" ? {} : {
          annual_tuition: cleanNumber(requirement.annual_tuition),
          currency: requirement.currency,
        }),
        ...(language ? { minimum_language: language } : {}),
        transfer_policy: requirement.transfer_policy,
        ...(requirement.source ? {
          evidence_report_id: parts[0], evidence_citation: parts[1],
        } : {}),
      };
      const updated = await api<StudySchool>(
        target + "/universities/" + encodeURIComponent(selected) + "/requirements",
        "PATCH", body,
      );
      setSchools(old => old.map(s => s.id === updated.id ? updated : s));
      setMatches(await api<ComparisonResponse>(target + "/matches"));
      setNotice("Criteria saved and compared. Source attachment is not official verification.");
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  return <section className="rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-4 sm:p-5"
    aria-label="Program fit assessment">
    <h2 className="flex items-center gap-2 text-base font-semibold">
      <Scale size={18} className="text-[var(--aq-blue)]"/> Program Fit & Eligibility Gap Engine
    </h2>
    <p className="mt-2 text-xs leading-5 text-[var(--aq-muted)]">
      Real comparisons run on the backend, using your saved academic facts and the
      program criteria you review. This is not an acceptance score or an eligibility decision.
    </p>
    <div className="mt-3 flex flex-wrap gap-2">
      <button type="button" onClick={onResearch} disabled={!researchAllowed || busy}
        className={buttonClass} title={researchAllowed ? undefined : "Enable external research consent below first"}>
        Research university sources
      </button>
      <button type="button" onClick={() => { void api<ComparisonResponse>(target + "/matches")
        .then(setMatches).catch(e => setError(String(e))); }}
        className={buttonClass} disabled={busy || loading}>
        <RefreshCw size={13} className="mr-1 inline"/> Recalculate fit
      </button>
    </div>
    {error && <p role="alert" className="mt-3 text-xs text-red-400">{error}</p>}
    {notice && <p role="status" className="mt-3 text-xs text-[var(--aq-muted)]">{notice}</p>}
    {loading && <p role="status" className="mt-3 text-xs text-[var(--aq-muted)]">Loading saved academic facts…</p>}

    <form className="mt-4 rounded-xl border border-[var(--aq-border)] p-3" onSubmit={saveProfile}>
      <h3 className="text-sm font-semibold">1. My academic and budget profile</h3>
      <p className="mt-1 text-[11px] text-[var(--aq-muted)]">Optional fields. Never enter passport, bank or ID numbers.</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="text-xs">GPA
          <input type="number" min="0" max="100" step="0.01" value={profile.gpa}
            onChange={e => setProfile(p => ({ ...p, gpa: e.target.value }))}
            className={fieldClass + " mt-1"} placeholder="3.50"/>
        </label>
        <label className="text-xs">Grading scale
          <select value={profile.gpa_scale} onChange={e => setProfile(p => ({ ...p, gpa_scale: e.target.value }))}
            className={fieldClass + " mt-1"}>
            {[4, 5, 10, 100].map(n => <option key={n} value={n}>Out of {n}</option>)}
          </select>
        </label>
        <label className="text-xs">Annual available budget
          <input type="number" min="0" step="1" value={profile.annual_budget}
            onChange={e => setProfile(p => ({ ...p, annual_budget: e.target.value }))}
            className={fieldClass + " mt-1"} placeholder="1200000"/>
        </label>
        <label className="text-xs">Budget currency
          <select value={profile.currency} onChange={e => setProfile(p => ({ ...p, currency: e.target.value }))}
            className={fieldClass + " mt-1"}>
            {currencyChoices.map(c => <option key={c}>{c}</option>)}
          </select>
        </label>
        <label className="text-xs">Language test
          <select value={profile.test} onChange={e => setProfile(p => ({ ...p, test: e.target.value }))}
            className={fieldClass + " mt-1"}>
            {testChoices.map(t => <option key={t} value={t}>{t || "Not entered"}</option>)}
          </select>
        </label>
        {profile.test === "JLPT" ? (
          <label className="text-xs">JLPT level
            <select value={profile.level} onChange={e => setProfile(p => ({ ...p, level: e.target.value }))}
              className={fieldClass + " mt-1"}>
              {["N5","N4","N3","N2","N1"].map(n => <option key={n}>{n}</option>)}
            </select>
          </label>
        ) : profile.test !== "" ? (
          <label className="text-xs">Test score
            <input required type="number" min="0" step="0.5" value={profile.score}
              onChange={e => setProfile(p => ({ ...p, score: e.target.value }))}
              className={fieldClass + " mt-1"} placeholder="6.5"/>
          </label>
        ) : null}
        <label className="flex items-center gap-2 text-xs sm:col-span-2">
          <input type="checkbox" checked={profile.transfer_requested}
            onChange={e => setProfile(p => ({ ...p, transfer_requested: e.target.checked }))}/>
          I want transfer/credit recognition
        </label>
        {profile.transfer_requested && (
          <label className="text-xs">Previously completed credits (optional)
            <input type="number" min="0" max="400" value={profile.completed_credits}
              onChange={e => setProfile(p => ({ ...p, completed_credits: e.target.value }))}
              className={fieldClass + " mt-1"} placeholder="60"/>
          </label>
        )}
      </div>
      <button type="submit" className={buttonClass + " mt-3"} disabled={busy}>
        Save & compare my facts
      </button>
    </form>

    {selected && <div className="mt-4 rounded-xl border border-[var(--aq-border)] p-3">
      <h3 className="text-sm font-semibold">Research this exact university</h3>
      <p className="mt-1 text-[11px] leading-5 text-[var(--aq-muted)]">
        Search live sources restricted to the shortlisted program&apos;s HTTPS hostname.
        Only the university and program labels, country, intake and hostname are sent
        externally after consent. The research may fail when official evidence is
        unavailable. Source text remains unverified until you review the original page.
      </p>
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <label className="min-w-40 flex-1 text-xs">
          Source research focus
          <select className={fieldClass + " mt-1"} value={evidenceTopic}
            onChange={event => setEvidenceTopic(event.target.value)}>
            {["admissions", "language", "costs", "transfer", "universities"].map(topic =>
              <option key={topic} value={topic}>{topic}</option>)}
          </select>
        </label>
        <button type="button" className={buttonClass}
          disabled={!researchAllowed || busy || loading}
          onClick={() => { void refreshOfficialSources(); }}
          title={researchAllowed ? undefined : "Enable external research consent in the section below"}>
          {busy ? "Researching…" : "Fetch university-domain evidence"}
        </button>
      </div>
      {!researchAllowed && <p className="mt-2 text-[11px] text-[var(--aq-muted)]">
        Enable external research consent in the Research section to use live sources.
      </p>}
    </div>}

    <form className="mt-4 rounded-xl border border-[var(--aq-border)] p-3" onSubmit={saveRequirements}>
      <h3 className="text-sm font-semibold">2. Compare actual program requirements</h3>
      <p className="mt-1 text-[11px] leading-5 text-[var(--aq-muted)]">
        Research the exact program and intake first. Enter only thresholds you have checked;
        selecting a saved citation records provenance but does not validate the claim.
      </p>
      <label className="mt-3 block text-xs">Shortlisted program
        <select value={selected} onChange={e => { setSelected(e.target.value); setSuggestions([]); }}
          className={fieldClass + " mt-1"}>
          {schools.length === 0 && <option value="">Add a university above to compare</option>}
          {schools.map(s => <option key={s.id} value={s.id}>{s.name} · {s.program}</option>)}
        </select>
      </label>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="text-xs">Published minimum GPA
          <input type="number" min="0" step="0.01" value={requirement.minimum_gpa}
            onChange={e => setRequirement(p => ({ ...p, minimum_gpa: e.target.value }))}
            className={fieldClass + " mt-1"} placeholder="3.00"/>
        </label>
        <label className="text-xs">Program GPA scale
          <select value={requirement.gpa_scale}
            onChange={e => setRequirement(p => ({ ...p, gpa_scale: e.target.value }))}
            className={fieldClass + " mt-1"}>
            {[4, 5, 10, 100].map(n => <option key={n} value={n}>Out of {n}</option>)}
          </select>
        </label>
        <label className="text-xs">Annual tuition
          <input type="number" min="0" step="1" value={requirement.annual_tuition}
            onChange={e => setRequirement(p => ({ ...p, annual_tuition: e.target.value }))}
            className={fieldClass + " mt-1"} placeholder="8000"/>
        </label>
        <label className="text-xs">Tuition currency
          <select value={requirement.currency}
            onChange={e => setRequirement(p => ({ ...p, currency: e.target.value }))}
            className={fieldClass + " mt-1"}>
            {currencyChoices.map(c => <option key={c}>{c}</option>)}
          </select>
        </label>
        <label className="text-xs">Required language test
          <select value={requirement.test}
            onChange={e => setRequirement(p => ({ ...p, test: e.target.value }))}
            className={fieldClass + " mt-1"}>
            {testChoices.map(t => <option key={t} value={t}>{t || "Not specified"}</option>)}
          </select>
        </label>
        {requirement.test === "JLPT" ? (
          <label className="text-xs">Minimum JLPT level
            <select value={requirement.level}
              onChange={e => setRequirement(p => ({ ...p, level: e.target.value }))}
              className={fieldClass + " mt-1"}>
              {["N5","N4","N3","N2","N1"].map(n => <option key={n}>{n}</option>)}
            </select>
          </label>
        ) : requirement.test !== "" ? (
          <label className="text-xs">Required score
            <input required type="number" min="0" step="0.5"
              value={requirement.score}
              onChange={e => setRequirement(p => ({ ...p, score: e.target.value }))}
              className={fieldClass + " mt-1"} placeholder="6.5"/>
          </label>
        ) : null}
        <label className="text-xs">Transfer admission pathway
          <select value={requirement.transfer_policy}
            onChange={e => setRequirement(p => ({ ...p, transfer_policy: e.target.value }))}
            className={fieldClass + " mt-1"}>
            <option value="unknown">Not confirmed</option>
            <option value="yes">Reported available</option>
            <option value="no">Reported unavailable</option>
          </select>
        </label>
      </div>
      <label className="mt-3 block text-xs">Relevant saved university citation (optional)
        <select value={requirement.source}
          onChange={e => setRequirement(p => ({ ...p, source: e.target.value }))}
          className={fieldClass + " mt-1"}>
          <option value="">No source linked yet</option>
          {evidence.map(o => <option value={o.value} key={o.value}>{o.label}</option>)}
        </select>
      </label>
      <button type="submit" className={buttonClass + " mt-3"} disabled={busy || !selected}>
        Save criteria & run gap analysis
      </button>
      <button type="button" className={buttonClass + " mt-3 ml-2"} disabled={!selected || busy}
        onClick={() => { void loadEvidenceDrafts(); }}>
        Extract draft thresholds from saved sources
      </button>
      {suggestions.length > 0 && <div className="mt-3 space-y-2" role="region"
        aria-label="Suggested criteria from first party sources">
        {suggestions.map(draft => (
          <div key={draft.report_id + draft.citation}
            className="rounded-lg border border-[var(--aq-border)] p-3 text-xs">
            <p className="font-semibold">{draft.citation} · Unverified excerpt proposal
              {draft.stale && <span className="ml-2 text-amber-400">Old source</span>}
            </p>
            <p className="mt-1 break-words text-[var(--aq-muted)]">
              {Object.entries(draft.suggested_facts).map(([key, value]) =>
                key + ": " + (typeof value === "object" ? JSON.stringify(value) : String(value))
              ).join(" · ")}
            </p>
            <p className="mt-1 text-[var(--aq-muted)]">{draft.note}</p>
            <div className="mt-2 flex flex-wrap gap-3">
              <a href={draft.source_url} target="_blank" rel="noopener noreferrer"
                className="text-[var(--aq-blue)]">Open original evidence</a>
              <button type="button" className={buttonClass} onClick={() => reviewSuggestion(draft)}>
                Review values in editable form
              </button>
            </div>
          </div>
        ))}
      </div>}

    </form>

    <div className="mt-4 space-y-3" aria-label="Computed university comparisons">
      <h3 className="text-sm font-semibold">3. Live comparison results</h3>
      {matches?.programs.length === 0 && (
        <p className="text-xs text-[var(--aq-muted)]">No shortlisted programs yet. Run university research and add exact program URLs above.</p>
      )}
      {matches?.programs.map(item => (
        <div key={item.university_id} className="rounded-xl border border-[var(--aq-border)] p-3">
          <h4 className="font-semibold text-sm">{item.university_name} · {item.program}</h4>
          <p className="mt-1 text-xs text-[var(--aq-muted)]">
            {item.matched_count} reported matches · {item.gap_count} possible gaps · {item.unknown_count} unknown
          </p>
          <p className="mt-1 text-xs text-[var(--aq-muted)]">
            {item.assessment === "possible_gaps" ? "Potential requirement gaps require review"
              : item.assessment === "potential_match_unverified" ? "Compared criteria align (unverified)"
                : "Not enough evidence for a comparison"}
          </p>
          <ul className="mt-3 space-y-2">
            {item.criteria.map(c => (
              <li key={c.criterion} className="rounded-lg bg-[var(--aq-card)] p-2 text-xs">
                <strong>{c.criterion.toUpperCase()}</strong>{" · "}
                <span className={c.status === "reported_gap" ? "text-amber-400" : "text-[var(--aq-muted)]"}>
                  {c.status.replaceAll("_", " ")}
                </span>
                <p className="mt-1 text-[var(--aq-muted)]">{c.detail}</p>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[11px] text-[var(--aq-muted)]">
            <ShieldCheck size={12} className="mr-1 inline"/>
            {item.provenance === "source_linked_unverified" ? "Saved source linked; claims not independently verified"
              : "User-entered criteria; source verification needed"}
            {item.source_stale ? " · Check latest intake" : ""}
          </p>
          {item.evidence_url && (
            <a href={item.evidence_url} target="_blank" rel="noopener noreferrer"
              className="mt-2 inline-flex items-center gap-1 text-xs text-[var(--aq-blue)]">
              Review linked source <ExternalLink size={12}/>
            </a>
          )}
        </div>
      ))}
      {matches && <p className="text-[11px] leading-5 text-[var(--aq-muted)]">
        {matches.disclaimer}
      </p>}
    </div>

    <StudyApplicationPacket caseId={caseId} universityId={selected} />
    {candidates.length > 0 && <div className="mt-4 rounded-xl border border-[var(--aq-border)] p-3">
      <h3 className="text-sm font-semibold">4. Real researched links to review</h3>
      <p className="mt-1 text-[11px] text-[var(--aq-muted)]">
        These are URLs returned by Web Research, not automatically verified programs.
        Open the link, confirm the actual university and course, then save it to your shortlist.
      </p>
      <div className="mt-3 space-y-2">
        {candidates.slice(0, 10).map(c => (
          <div className="flex flex-wrap items-center gap-2 text-xs" key={c.url}>
            <a className="min-w-0 flex-1 break-all text-[var(--aq-blue)]"
              href={c.url} target="_blank" rel="noopener noreferrer">
              {c.title} <ExternalLink size={11} className="inline"/>
            </a>
            <button type="button" className={buttonClass}
              onClick={() => onUseCandidate(c.url)}>
              Use link in shortlist form
            </button>
          </div>
        ))}
      </div>
    </div>}
  </section>;
}
