import assert from "node:assert/strict";
import test from "node:test";
import { getChatTools } from "../src/lib/chat-tools.ts";

test("composer menu orders file upload before research agents", () => {
  const tools = getChatTools("normal");
  assert.deepEqual(tools.map((tool) => tool.id),
    ["upload", "web", "browser", "knowledge", "documents"]);
  assert.equal(tools[0].href, undefined);
  assert.equal(tools[1].href, "/web");
  assert.equal(tools[2].href, "/agent/browser");
  assert.equal(tools[3].href, undefined);
  assert.equal(tools[4].href, undefined);
  assert.ok(tools.every((tool) => tool.label && tool.description));
});

test("mode toggle is contextual and does not navigate away", () => {
  const inKnowledge = getChatTools("knowledge");
  assert.equal(inKnowledge[3].label, "Switch to Converse");
  assert.equal(inKnowledge[3].href, undefined);
  assert.equal(getChatTools("normal")[3].label, "Knowledge chat");
});
