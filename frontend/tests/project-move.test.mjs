import test from "node:test";
import assert from "node:assert/strict";
import { projectsForConversation } from "../src/lib/conversation/project-move.ts";

test("Add to project lists only backend-compatible mode and preserves selected ID", () => {
  const all = [
    { id: "p-normal", name: "General", mode: "normal" },
    { id: "p-knowledge", name: "Research", mode: "knowledge" },
  ];
  assert.deepEqual(projectsForConversation(all, "normal").map(p => p.id), ["p-normal"]);
  assert.deepEqual(projectsForConversation(all, "knowledge").map(p => p.id), ["p-knowledge"]);
  assert.deepEqual(projectsForConversation([], "normal"), []);
});
