"use client";

import { useState } from "react";

type Packet = {
  university_name: string;
  program: string;
  applicant_draft: Record<string, unknown>;
  ready_document_categories: string[];
  outstanding_checklist: { key: string; title: string; state: string }[];
  unresolved_program_criteria: { criterion: string; status: string; detail: string }[];
  submission_status: "not_submitted";
  requires_explicit_user_review: boolean;
  disclaimer: string;
};

export function StudyApplicationPacket({
  caseId, universityId,
}: { caseId: string; universityId: string }) {
  const [packet, setPacket] = useState<Packet | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function generate() {
    if (!universityId) return;
    setBusy(true); setMessage("");
    try {
      const path = "/api/study-abroad/cases/" + encodeURIComponent(caseId) +
        "/universities/" + encodeURIComponent(universityId) + "/application-preview";
      const response = await fetch(path, { cache: "no-store" });
      if (!response.ok) throw new Error("Could not generate private application draft");
      const data = await response.json() as Packet;
      if (data.submission_status !== "not_submitted" ||
          !data.requires_explicit_user_review) {
        throw new Error("Unexpected application draft approval state");
      }
      setPacket(data);
    } catch (error) {
      setMessage(String(error));
    } finally {
      setBusy(false);
    }
  }

  return <section className="mt-4 rounded-xl border border-[var(--aq-border)] p-3"
    aria-label="Application preparation agent">
    <h3 className="text-sm font-semibold">Application agent · actual private review packet</h3>
    <p className="mt-1 text-[11px] leading-5 text-[var(--aq-muted)]">
      Compiles saved applicant facts, uploaded-document categories and unresolved
      admission criteria. No external submission, messages or document sharing.
    </p>
    <button type="button" disabled={!universityId || busy}
      onClick={() => { void generate(); }}
      className="mt-3 min-h-10 rounded-lg border border-[var(--aq-blue)] px-3 py-2 text-xs text-[var(--aq-blue)] disabled:opacity-50">
      {busy ? "Preparing…" : "Prepare application review"}
    </button>
    {message && <p role="status" className="mt-2 text-xs text-[var(--aq-muted)]">{message}</p>}
    {packet && <div className="mt-3 space-y-2 text-xs">
      <p className="font-semibold">{packet.university_name} · {packet.program}</p>
      <pre className="max-w-full overflow-x-auto whitespace-pre-wrap break-words rounded-lg bg-[var(--aq-card)] p-3 text-[11px]">
        {JSON.stringify(packet.applicant_draft, null, 2)}
      </pre>
      <p>Linked ready categories: {packet.ready_document_categories.join(", ") || "None"}</p>
      <p className="font-semibold">Outstanding document/checklist checks</p>
      <ul className="list-disc pl-5">
        {packet.outstanding_checklist.map(item => (
          <li key={item.key}>{item.title} · {item.state}</li>
        ))}
      </ul>
      <p className="font-semibold">Unresolved degree/program conditions</p>
      <ul className="list-disc pl-5">
        {packet.unresolved_program_criteria.map(item => (
          <li key={item.criterion}>{item.detail}</li>
        ))}
      </ul>
      <p className="text-amber-400">NOT SUBMITTED · Explicit user review required.</p>
      <p className="text-[var(--aq-muted)]">{packet.disclaimer}</p>
      <button type="button" className="rounded-lg border border-[var(--aq-border)] px-3 py-2"
        onClick={() => { void navigator.clipboard.writeText(JSON.stringify(packet, null, 2))
          .then(() => setMessage("Application review copied"))
          .catch(() => setMessage("Clipboard unavailable; select the text above")); }}>
        Copy review packet
      </button>
    </div>}
  </section>;
}
