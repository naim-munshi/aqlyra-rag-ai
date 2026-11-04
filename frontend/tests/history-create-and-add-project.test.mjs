import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const history = readFileSync(
  new URL("../src/components/workspace/conversation-history.tsx", import.meta.url),
  "utf8",
);
const sidebar = readFileSync(
  new URL("../src/components/workspace/sidebar.tsx", import.meta.url),
  "utf8",
);

test("history offers create-and-add even if no project exists yet", () => {
  assert.match(history, /Create new project & add/);
  assert.match(history, /No projects yet/);
  assert.match(history, /function createProjectFromConversation/);
  // The create button is outside the existing-project conditional.
  const start = history.indexOf("visibleProjects.length > 0 ? (");
  const end = history.indexOf('className="my-1 border-t', start);
  const menu = history.slice(start, end);
  assert.match(menu, /\) : \([\s\S]*No projects yet[\s\S]*\)\}[\s\S]*Create new project & add/);
});

test("create-and-add uses the existing APIs with the selected conversation mode", () => {
  const start = history.indexOf("async function createProjectFromConversation(");
  const end = history.indexOf("async function copyConversation(", start);
  const action = history.slice(start, end);
  assert.match(action, /fetch\("\/api\/projects",/);
  assert.match(action, /method: "POST"/);
  assert.match(action, /mode: conversation\.mode/);
  assert.match(action, /patchConversation\(\s*conversation\.id,[\s\S]*project_id: data\.id/);
  assert.doesNotMatch(action, /fetch\("\/api\/conversations",/);
  assert.doesNotMatch(action, /method: "DELETE"/);
});

test("preserves existing project picker and safely reports partial failures", () => {
  assert.match(history, /visibleProjects\.map/);
  assert.match(history, /void moveConversation/);
  assert.match(history, /this conversation was not moved/);
  assert.match(history, /Try Add to project again/);
  assert.match(history, /setCollapsedProjectIds/);
  assert.match(history, /creatingProjectForConversationId !== null/);
});

test("global new-project entry still creates an empty chat as before", () => {
  assert.match(sidebar, /function createProject\(/);
  assert.match(sidebar, /project_id: project\.id/);
});
