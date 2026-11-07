import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
const wrapper = readFileSync(
  new URL("../src/components/study-abroad/study-abroad-workspace.tsx", import.meta.url), "utf8",
);
const workbench = readFileSync(
  new URL("../src/components/study-abroad/program-fit-workbench.tsx", import.meta.url), "utf8",
);

test("Study Abroad actually calls backend matching, applicant and requirements APIs", () => {
  assert.match(wrapper, /<StudyFitWorkbench/);
  assert.match(workbench, /target \+ "\/matches"/);
  assert.match(workbench, /target \+ "\/applicant-facts", "PATCH"/);
  assert.match(workbench, /"\/requirements"/);
  assert.match(workbench, /matched_count/);
  assert.match(workbench, /reported_gap/);
  assert.match(workbench, /unknown_count/);
});

test("research candidates are actual source URLs, not made-up school profiles", () => {
  assert.match(workbench, /target \+ "\/program-candidates"/);
  assert.match(workbench, /Use link in shortlist form/);
  assert.match(wrapper, /setUniversityForm\(\{ name: "", program: "", program_url: url, deadline: "" \}\)/);
  assert.match(workbench, /not automatically verified programs/);
});

test("UI requires deliberate submission of profile and criteria, never predicts admission", () => {
  assert.match(workbench, /onSubmit=\{saveProfile\}/);
  assert.match(workbench, /onSubmit=\{saveRequirements\}/);
  assert.match(workbench, /not an acceptance score or an eligibility decision/);
  assert.match(workbench, /Source attachment is not official verification/);
});

test("untrusted excerpts only prefill drafts with a user click, not silent backend writes", () => {
  assert.match(workbench, /requirement-suggestions/);
  assert.match(workbench, /loadEvidenceDrafts/);
  assert.match(workbench, /reviewSuggestion\(draft\)/);
  assert.match(workbench, /Open original evidence/);
  assert.match(workbench, /Confirm the full university page/);
  assert.match(workbench, /Save criteria to persist/);
});

test("academic document audit calls actual linked-file RAG only with permission", () => {
  assert.match(wrapper, /async function analyzeLinkedAcademicRecords\(\)/);
  assert.match(wrapper, /"\/ask-documents", "POST"/);
  assert.match(wrapper, /confirm_share_documents: documentConsent/);
  assert.match(wrapper, /Mark anything unmentioned as unknown/);
  assert.match(wrapper, /Analyze my transcripts & identify missing evidence/);
});

test("application agent is an actual protected backend packet, never auto submit", () => {
  const source = readFileSync(
    new URL("../src/components/study-abroad/application-packet.tsx", import.meta.url), "utf8",
  );
  assert.match(workbench, /<StudyApplicationPacket caseId=\{caseId\}/);
  assert.match(source, /"\/application-preview"/);
  assert.match(source, /submission_status !== "not_submitted"/);
  assert.match(source, /NOT SUBMITTED/);
  assert.match(source, /Copy review packet/);
});


test("university evidence refresh executes real opt-in scoped API, never autosaves criteria", () => {
  assert.match(workbench, /"\/refresh-evidence"/);
  assert.match(workbench, /confirm_share_program: true/);
  assert.match(workbench, /!selected \|\| !researchAllowed/);
  assert.match(workbench, /Fetch university-domain evidence/);
  assert.match(workbench, /setSuggestions\(result\.suggestions\)/);
  assert.match(workbench, /onEvidenceUpdated\(\)/);
  assert.match(wrapper, /onEvidenceUpdated=\{refreshAdvisor\}/);
});


test("program fit integrates without replacing chat-first navigation", () => {
  const chat = wrapper.indexOf('aria-label="Ask Aqlyra study assistant"');
  const nav = wrapper.indexOf('aria-label="Study plan navigation"');
  const fit = wrapper.indexOf("<StudyFitWorkbench");
  assert.ok(chat > 0 && nav > chat && fit > nav);
  assert.ok(wrapper.includes('activePanel === "universities" && ('));
  assert.ok(wrapper.includes("researchAllowed={researchConsent}"));
  assert.ok(wrapper.includes("onEvidenceUpdated={refreshAdvisor}"));
});


test("evidence selection mirrors backend URL credential and port restrictions", () => {
  assert.match(workbench, /a\\.username \\|\\| a\\.password/);
  assert.match(workbench, /b\\.username \\|\\| b\\.password/);
  assert.match(workbench, /a\\.port && a\\.port !== "443"/);
  assert.match(workbench, /b\\.port && b\\.port !== "443"/);
  assert.match(workbench, /\\/\\\\s\\//);
});
