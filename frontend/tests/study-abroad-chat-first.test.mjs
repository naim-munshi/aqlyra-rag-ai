import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const ui = readFileSync(
  new URL("../src/components/study-abroad/study-abroad-workspace.tsx", import.meta.url),
  "utf8",
);

test("Study Abroad starts with Ask Aqlyra and retains optional navigation", () => {
  const chatIndex = ui.indexOf('aria-label="Ask Aqlyra study assistant"');
  const navIndex = ui.indexOf('aria-label="Study plan navigation"');
  assert.ok(chatIndex > 0, "Chat should exist");
  assert.ok(navIndex > chatIndex, "Navigation follows the chat");
  for (const section of ["overview", "universities", "research", "documents"]) {
    assert.match(ui, new RegExp('activePanel !== "' + section + '"'));
  }
  assert.match(ui, /"My plan"/);
  assert.match(ui, /"Explore topics"/);
  assert.match(ui, /"Documents"/);
  assert.doesNotMatch(ui, /Student Visa · Available|Job Visa · Planned/);
});

test("Chat research is functional, source-grounded and explicitly opt-in", () => {
  assert.match(ui, /function inferResearchTopic\(text: string\)/);
  assert.match(ui, /async function sendStudyChat\(event: FormEvent<HTMLFormElement>\)/);
  assert.match(ui, /research\(topic, researchFocusId, question\)/);
  assert.match(ui, /if \(!researchConsent \|\| question\.length < 12 \|\| question\.length > 160\) return/);
  assert.match(ui, /confirm_share_profile: researchConsent/);
  assert.match(ui, /setReports\(previous => \[result, \.\.\.previous\]\)/);
  assert.match(ui, /<MarkdownMessage content=\{report\.answer\}/);
  assert.match(ui, /report\.sources\.slice\(0, 5\)/);
  assert.match(ui, /No uploaded files or private notes are shared/);
});

test("Document chat reuses owner-isolated RAG without implicitly consenting", () => {
  assert.match(ui, /if \(!documentConsent \|\| documents\.length === 0 \|\| question\.length < 5/);
  assert.match(ui, /"cases\/" \+ active\.id \+ "\/ask-documents"/);
  assert.match(ui, /confirm_share_documents: documentConsent/);
  assert.match(ui, /chatSource === "documents" && documentAnswer/);
  assert.match(ui, /setLastDocumentChatQuestion\(question\)/);
  assert.match(ui, /setDocumentAnswer\(null\); setDocumentConsent\(false\); setResearchConsent\(false\)/); // isolated when switching plans
});

test("Conversational setup saves only after all six answers and keeps original form", () => {
  for (const key of ["nationality", "residence_country", "destination_country",
    "degree_level", "study_field", "intake"]) {
    assert.match(ui, new RegExp('key: "' + key + '"'));
  }
  assert.match(ui, /async function submitSetupReply\(event: FormEvent<HTMLFormElement>\)/);
  assert.match(ui, /setupStep === CHAT_SETUP_STEPS\.length - 1/);
  assert.match(ui, /await saveStudyCase\(updated\)/);
  assert.match(ui, /async function createCase\(event: FormEvent<HTMLFormElement>\)/);
  assert.match(ui, /Prefer a form\? Use guided setup/);
  assert.match(ui, /Create student journey/);
});

test("Changing plans clears transient chat answers but keeps saved data", () => {
  assert.match(ui, /setChatQuestion\(""\); setLastDocumentChatQuestion\(""\); setActivePanel\("overview"\)/);
  assert.match(ui, /api<StudyReport\[\]>\("cases\/" \+ id \+ "\/research"\)/);
  assert.match(ui, /setReports\(research\)/);
  assert.match(ui, /setUniversities\(shortlist\)/);
  assert.match(ui, /setDocuments\(files\)/);
});
