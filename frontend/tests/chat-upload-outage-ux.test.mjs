import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const workspace = readFileSync(
  new URL("../src/components/chat/rag-workspace.tsx", import.meta.url),
  "utf8"
);

test("ephemeral upload outage has a safe actionable UX message", () => {
  assert.match(workspace, /uploadResponse\.status === 503/);
  assert.match(workspace, /Secure file uploads are temporarily unavailable/);
  assert.match(workspace, /You can still chat without a file/);
});

test("chat composer removes stale errors after typing and permits dismissal", () => {
  assert.match(workspace, /if \(attachmentError\) setAttachmentError\(""\)/);
  assert.match(workspace, /aria-label="Dismiss attachment error"/);
  assert.match(workspace, /role="alert"/);
  assert.match(workspace, /onClick=\{\(\) => setAttachmentError\(""\)\}/);
});
