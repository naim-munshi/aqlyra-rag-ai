import assert from "node:assert/strict";
import test from "node:test";
import { getChatTools, getChatToolsMenuPosition } from "../src/lib/chat-tools.ts";

test("composer menu orders file upload before research agents", () => {
  const tools = getChatTools("normal");
  assert.deepEqual(tools.map((tool) => tool.id),
    ["upload", "web", "web-deep", "web-off", "browser", "knowledge", "documents"]);
  assert.equal(tools[0].href, undefined);
  assert.equal(tools[1].href, undefined); // In-chat web toggle, never /web.
  assert.equal(tools[2].href, undefined); // In-chat deep research.
  assert.equal(tools[3].href, undefined); // Explicit no-web mode.
  assert.equal(tools[4].href, "/agent/browser");
  assert.equal(tools[5].href, undefined);
  assert.ok(tools.every((tool) => tool.label && tool.description));
  assert.equal(tools.some((tool) => tool.id === "study"), false);
});

test("mode toggle is contextual and does not navigate away", () => {
  const inKnowledge = getChatTools("knowledge");
  assert.equal(inKnowledge[5].label, "Switch to Converse");
  assert.equal(inKnowledge[5].href, undefined);
  assert.equal(getChatTools("normal")[5].label, "Knowledge chat");
});

test("menu is always anchored above the composer with a usable fixed width", () => {
  const desktop = getChatToolsMenuPosition(
    { left: 628, top: 600 }, 1526, 991,
  );
  assert.deepEqual(desktop, {
    left: 628, width: 280, bottom: 401, maxHeight: 320,
  });
  const mobile = getChatToolsMenuPosition(
    { left: 14, top: 700 }, 375, 812,
  );
  assert.deepEqual(mobile, {
    left: 14, width: 280, bottom: 122, maxHeight: 320,
  });
  const edge = getChatToolsMenuPosition(
    { left: 380, top: 530 }, 400, 800,
  );
  assert.equal(edge.left + edge.width <= 388, true);
  assert.equal(edge.bottom > 0, true);
});

test("search and deep research stay in the same chat instead of opening a workspace", () => {
  const tools = getChatTools("normal");
  for (const id of ["web", "web-deep", "web-off"]) {
    const tool = tools.find((entry) => entry.id === id);
    assert.ok(tool);
    assert.equal(tool.href, undefined);
  }
});
