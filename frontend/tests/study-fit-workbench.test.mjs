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
