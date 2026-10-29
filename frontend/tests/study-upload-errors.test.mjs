import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { studyUploadErrorMessage } from "../src/lib/study-upload-errors.ts";

test("Study Abroad upload errors describe the real failure without echoing providers", () => {
  const cases = [
    [401, "session expired"],
    [413, "too large"],
    [415, "Unsupported file format"],
    [429, "Too many upload attempts"],
    [503, "storage is temporarily unavailable"],
    [500, "Document upload failed"],
  ];
  for (const [status, fragment] of cases) {
    const actual = studyUploadErrorMessage(status);
    assert.ok(actual.includes(fragment), String(status));
    assert.ok(actual.length <= 120, "short and actionable");
    assert.doesNotMatch(actual, /secret|token|bucket|S3|quota.billing/i);
  }
});

test("Only confirmed HTTP 409 duplicate uploads can attach a prior document", () => {
  const file = fileURLToPath(
    new URL("../src/components/study-abroad/study-abroad-workspace.tsx", import.meta.url)
  );
  const source = readFileSync(file, "utf8");
  assert.match(source, /result\.status === 409 && raw/);
  assert.match(source, /typeof raw\.detail\.document_id === "string"/);
  assert.match(source, /studyUploadErrorMessage\(result\.status\)/);
  assert.match(source, /result\.json\(\)\.catch\(\(\) => null\)/);
  assert.doesNotMatch(source, /Upload failed\. Use a supported file under 25 MiB/);
});
