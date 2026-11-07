import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const wrapper = readFileSync(
  new URL("../src/components/study-abroad/study-abroad-workspace.tsx", import.meta.url), "utf8",
);
const brief = readFileSync(
  new URL("../src/components/study-abroad/study-evidence-brief.tsx", import.meta.url), "utf8",
);
const proxy = readFileSync(
  new URL("../src/app/api/study-abroad/[...path]/route.ts", import.meta.url), "utf8",
);

test("actual case-scoped readiness endpoint is callable in the existing chat-first UI", () => {
  assert.match(wrapper, /<StudyEvidenceBrief/);
  assert.match(wrapper, /caseId=\{active\.id\}/);
  assert.match(wrapper, /key=\{active\.id \+ ":" \+ advisorRevision\}/);
  assert.match(wrapper, /onNavigate=\{setActivePanel\}/);
  assert.ok(wrapper.indexOf('<nav className="flex gap-2') < wrapper.indexOf("<StudyEvidenceBrief"));
  assert.ok(wrapper.indexOf("<StudyEvidenceBrief") < wrapper.indexOf("Smart Study Advisor"));
  assert.match(brief, /fetch\(/);
  assert.match(brief, /"\/api\/study-abroad\/cases\/"/);
  assert.match(brief, /"\/evidence-brief"/);
  assert.match(brief, /response\.ok/);
  assert.match(brief, /data\.case_id !== caseId/);
  assert.match(proxy, /getAccessToken/);
  assert.match(proxy, /hasTrustedRequestOrigin/);
});

test("brief distinguishes known gaps, unknowns, provenance, and private files", () => {
  for (const value of [
    "programs_with_reported_gaps",
    "unresolved_program_criteria",
    "linked_ready_documents",
    "stale_research_topics",
    "needs_review",
    "saved_source_links",
    "linked_categories",
    "next_actions",
  ]) assert.ok(brief.includes(value), value);
  assert.match(brief, /No external search or file sharing/);
  assert.match(brief, /not independently verified/);
  assert.match(brief, /target="_blank" rel="noopener noreferrer"/);
  assert.match(brief, /onNavigate\("universities"\)/);
  assert.match(brief, /onNavigate\("research"\)/);
  assert.match(brief, /onNavigate\("documents"\)/);
});

test("readiness never claims to automatically share private documents or submit an application", () => {
  assert.doesNotMatch(brief, /method:\s*"POST"/);
  assert.doesNotMatch(brief, /"\/api\/documents\/.*\/content"/);
  assert.doesNotMatch(brief, /navigator\.sendBeacon|localStorage/);
  assert.match(brief, /caseId: string/);
});
