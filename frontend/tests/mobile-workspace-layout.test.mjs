import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path) => readFileSync(new URL("../src/" + path, import.meta.url), "utf8");

test("mobile home uses one responsive navigation drawer, not fixed desktop sidebar width", () => {
  const home = read("app/page.tsx");
  const shell = read("components/workspace/responsive-workspace-shell.tsx");
  const nav = read("components/workspace/sidebar.tsx");
  assert.match(home, /<ResponsiveWorkspaceShell user=\{user\}/);
  assert.doesNotMatch(home, /<Sidebar user=\{user\}/);
  assert.match(shell, /fixed inset-y-0 left-0/);
  assert.match(shell, /md:static/);
  assert.match(shell, /invisible -translate-x-full md:visible/);
  assert.match(shell, /Close navigation drawer/);
  assert.match(shell, /Escape/);
  assert.match(nav, /h-full w-full/);
});

test("phone chat fills viewport and composer remains usable", () => {
  const pane = read("components/workspace/knowledge-workspace.tsx");
  const chat = read("components/chat/rag-workspace.tsx");
  const viewport = read("app/layout.tsx");
  assert.match(pane, /Open navigation/);
  assert.match(pane, /md:hidden/);
  assert.match(pane, /min-h-0 min-w-0 flex-1/);
  assert.match(chat, /min-h-0 min-w-0 w-full overflow-hidden/);
  assert.match(chat, /env\(safe-area-inset-bottom\)/);
  assert.match(chat, /w-\[min\(100%,360px\)\]/);
  assert.match(viewport, /width: "device-width"/);
});
