import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const documents = readFileSync(
  new URL("../src/components/documents/document-panel.tsx", import.meta.url),
  "utf8",
);

function extractBetween(start, end) {
  const a = documents.indexOf(start);
  const b = documents.indexOf(end, a);
  assert.ok(a >= 0 && b > a, "expected handler exists");
  return documents.slice(a, b);
}

test("Documents picker supports multiple selected files, bounded to 10", () => {
  assert.match(documents, /type="file"\s+multiple\s+accept=/);
  assert.match(documents, /MAX_BATCH_FILES = 10/);
  const code = extractBetween("async function handleFileChange(", "\n  return (\n    <section");
  assert.match(code, /Array\.from\(event\.target\.files \?\? \[\]\)/);
  assert.match(code, /event\.target\.value = ""/);
  assert.match(code, /if \(files\.length > MAX_BATCH_FILES\)/);
  assert.match(code, /No files were uploaded/);
  assert.doesNotMatch(code, /event\.target\.files\?\.\[0\]/);
});

test("private cloud upload and existing backend upload are reused per file", () => {
  const code = extractBetween("async function handleFileChange(", "\n  return (\n    <section");
  assert.match(code, /for \(const \[index, file\] of files\.entries\(\)\)/);
  assert.match(code, /uploadViaPrivateCloud\(file\)/);
  assert.match(code, /formData\.append\("file", file\)/);
  assert.match(code, /fetch\("\/api\/documents\/upload"/);
  assert.doesNotMatch(code, /Promise\.all/);
  assert.match(code, /await processDocument\(uploadedDocument\.id\)/);
});

test("one failing upload does not discard saved documents or stop later files", () => {
  const code = extractBetween("async function handleFileChange(", "\n  return (\n    <section");
  assert.match(code, /const failures: string\[\] = \[\]/);
  assert.match(code, /failures\.push/);
  assert.match(code, /setDocuments\(\(current\) => \[/);
  assert.match(code, /current\.filter/);
  assert.match(code, /setRecoveryNotice/);
  assert.match(code, /file\(s\) saved/);
  assert.match(code, /saved but indexing did not complete/);
  assert.match(code, /finally \{[\s\S]*setUploading\(false\)/);
  assert.doesNotMatch(code, /method: "DELETE"/);
});

test("queued documents are not claimed to be indexed successfully", () => {
  const code = extractBetween("async function handleFileChange(", "\n  return (\n    <section");
  assert.match(code, /uploadedDocument\.status === "queued"/);
  assert.match(code, /uploadedDocument\.status === "processing"/);
  assert.match(code, /queued \+= 1/);
  assert.match(code, /const indexed = await processDocument/);
  assert.match(code, /if \(!indexed\)/);
  assert.match(code, /indexingFailed \+= 1/);
});

test("UI announces upload progress and protects against duplicate submissions", () => {
  assert.match(documents, /aria-live="polite"/);
  assert.match(documents, /Uploading \$\{index \+ 1\}\/\$\{files\.length\}/);
  assert.match(documents, /Indexing \$\{index \+ 1\}\/\$\{files\.length\}/);
  assert.match(documents, /disabled=\{uploading\}/);
  assert.match(documents, /if \(files\.length === 0 \|\| uploading\)/);
});

test("single-file manual processing remains available", () => {
  const code = extractBetween("async function processDocument(", "async function retryIndex(");
  assert.match(code, /return false/);
  assert.match(code, /return true/);
  assert.match(documents, /Retry indexing/);
});
