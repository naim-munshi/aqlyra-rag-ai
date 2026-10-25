import assert from "node:assert/strict";
import test from "node:test";
import { parseResearchRequest } from "../src/lib/web/research-request.ts";

test("accepts normal and advanced research requests", () => {
  assert.deepEqual(parseResearchRequest({
    question: "  What changed recently?  ",
    max_sources: 3,
    mode: "deep",
  }), {
    question: "What changed recently?",
    max_sources: 3,
    mode: "deep",
  });
  assert.equal(parseResearchRequest({
    question: "Compare current findings",
    mode: "compare",
  })?.max_sources, 4);
});

test("URL mode requires a public HTTPS URL-shaped input", () => {
  assert.deepEqual(parseResearchRequest({
    question: "Summarize this page",
    mode: "url",
    source_url: "  https://example.com/paper  ",
  }), {
    question: "Summarize this page",
    mode: "url",
    source_url: "https://example.com/paper",
    max_sources: 4,
  });
  for (const input of [
    { question: "Read page", mode: "url" },
    { question: "Read page", mode: "url", source_url: "file:///etc/passwd" },
    { question: "Read page", mode: "url", source_url: "http://example.com" },
    { question: "Read page", mode: "search", source_url: "https://example.com" },
  ]) {
    assert.equal(parseResearchRequest(input), null);
  }
});

test("rejects unknown modes, malformed bodies and overlong questions", () => {
  for (const input of [
    null, [], "", { question: "x" },
    { question: "What happened?", mode: "arbitrary" },
    { question: "What happened?", max_sources: 500 },
    { question: "What happened?", max_sources: 1.5 },
    { question: "x".repeat(601) },
  ]) {
    assert.equal(parseResearchRequest(input), null);
  }
});
