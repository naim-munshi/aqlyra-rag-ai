import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
const source = readFileSync(
  new URL("../src/components/study-abroad/study-abroad-workspace.tsx", import.meta.url), "utf8",
);
test("personal study advisor is case-scoped, updates after changes, and never claims eligibility", () => {
  assert.match(source, /api<StudyAdvisor>\("cases\/" \+ id \+ "\/advisor"\)/);
  assert.match(source, /\[activeId, advisorRevision\]/);
  assert.match(source, /refreshAdvisor\(\)/);
  assert.match(source, /Smart Study Advisor/);
  assert.match(source, /User-entered date/);
  assert.match(source, /does not predict acceptance or visa approval/);
  assert.match(source, /Research with cited sources/);
});
test("focus research shares only approved university/program and requires explicit consent", () => {
  assert.match(source, /focus_university_id: focusUniversityId/);
  assert.match(source, /researchConsent/);
  assert.match(source, /!researchConsent/);
  assert.match(source, /private notes and files are not/);
  assert.match(source, /Transfer \/ credit admissions/);
  assert.match(source, /Tuition & living costs/);
  assert.match(source, /Language requirements/);
});

test("open-question research is bounded, consent gated and scoped to selected program", () => {
  assert.match(source, /Ask a specific study question/);
  assert.match(source, /specific_question: question\.trim\(\)/);
  assert.match(source, /maxLength=\{160\}/);
  assert.match(source, /minLength=\{12\}/);
  assert.match(source, /!researchConsent \|\| specificQuestion\.trim\(\)\.length < 12/);
  assert.match(source, /research\(customTopic, researchFocusId, specificQuestion\)/);
  assert.match(source, /setSpecificQuestion\(""\)/);
});
