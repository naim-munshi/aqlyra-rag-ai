import assert from "node:assert/strict";
import test from "node:test";

import {
  findScenario,
  previewScenarios,
  scenariosForMode,
} from "../src/lib/demo/scenarios.ts";

test("portfolio preview provides both knowledge and converse sample paths", () => {
  assert.ok(scenariosForMode("knowledge").length >= 3);
  assert.ok(scenariosForMode("converse").length >= 2);
  assert.equal(scenariosForMode("knowledge").length + scenariosForMode("converse").length, previewScenarios.length);
});

test("sample IDs and prompts are distinct, explicit and nonempty", () => {
  assert.equal(new Set(previewScenarios.map((item) => item.id)).size, previewScenarios.length);
  assert.equal(new Set(previewScenarios.map((item) => item.prompt.toLowerCase())).size, previewScenarios.length);
  for (const scenario of previewScenarios) {
    assert.ok(scenario.title.trim());
    assert.ok(scenario.prompt.trim());
    assert.ok(scenario.answer.trim());
    assert.ok(scenario.reasoningNote.trim());
    assert.equal(findScenario(scenario.id), scenario);
  }
});

test("knowledge demonstrations carry the citation context displayed in the UI", () => {
  for (const scenario of scenariosForMode("knowledge")) {
    assert.ok(scenario.fileName);
    assert.ok(scenario.sourceHeading);
    assert.ok(scenario.sourceExcerpt);
    assert.match(scenario.answer, /\[S1\]/);
  }
});

test("converse examples do not invent retrieved-document evidence", () => {
  for (const scenario of scenariosForMode("converse")) {
    assert.equal(scenario.fileName, null);
    assert.equal(scenario.sourceHeading, null);
    assert.equal(scenario.sourceExcerpt, null);
    assert.doesNotMatch(scenario.answer, /\[S1\]/);
  }
});

test("unknown scenario IDs resolve to no sample", () => {
  assert.equal(findScenario("not-real"), undefined);
});
