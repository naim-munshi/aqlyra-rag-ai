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
  assert.match(documentsPanel, /data-testid="documents-scroll-region"/);
  assert.match(documentsPanel, /role="region"/);
  assert.match(documentsPanel, /aria-label="Your documents"/);
});

test("the document list is independently scrollable with touch and keyboard support", () => {
  assert.match(
    documentsPanel,
    /overflow-x-hidden overflow-y-auto overscroll-y-contain touch-pan-y/,
  );
  assert.match(documentsPanel, /tabIndex=\{0\}/);
});

test("scroll behavior stays inside the Documents drawer, not the main chat panel", () => {
  assert.match(
    ragWorkspace,
    /<div className="relative flex h-full min-h-0 overflow-hidden">/,
  );
  assert.match(
    ragWorkspace,
    /"aq-panel flex min-h-0 flex-1 flex-col overflow-hidden transition-\[padding\] duration-200"/,
  );
  assert.match(ragWorkspace, /<DocumentPanel/);
  assert.match(ragWorkspace, /className="min-h-0 flex-1 p-3"/);
  assert.doesNotMatch(ragWorkspace, /documents-scroll-region/);
});
