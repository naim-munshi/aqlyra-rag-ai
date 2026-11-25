import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const documentsPanel = readFileSync(
  new URL("../src/components/documents/document-panel.tsx", import.meta.url),
  "utf8",
);
const ragWorkspace = readFileSync(
  new URL("../src/components/chat/rag-workspace.tsx", import.meta.url),
  "utf8",
);

test("Documents panel creates a bounded flex column for its list", () => {
  assert.match(
    documentsPanel,
    /<section className="aq-panel flex h-full min-h-0 w-full flex-col overflow-hidden p-4">/,
  );
  assert.ok(documentsPanel.includes('data-testid="documents-scroll-region"'));
  assert.ok(documentsPanel.includes('role="region"'));
  assert.ok(documentsPanel.includes('aria-label="Your documents"'));
});

test("the document list is independently scrollable with touch and keyboard support", () => {
  assert.ok(
    documentsPanel.includes(
      "overflow-x-hidden overflow-y-auto overscroll-y-contain touch-pan-y",
    ),
  );
  assert.ok(documentsPanel.includes("tabIndex={0}"));
});

test("scroll behavior stays inside the Documents drawer, not the main chat panel", () => {
  assert.ok(ragWorkspace.includes("<DocumentPanel"));
  assert.ok(ragWorkspace.includes('className="min-h-0 flex-1 p-3"'));
  assert.ok(!ragWorkspace.includes("documents-scroll-region"));
});
