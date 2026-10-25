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

test("bounded trusted domain filters and time windows are forwarded", () => {
  assert.deepEqual(parseResearchRequest({
    question: "Recent Python release security notes",
    mode: "deep",
    time_range: "month",
    include_domains: [" DOCS.PYTHON.ORG ", "python.org"],
  }), {
    question: "Recent Python release security notes",
    max_sources: 4,
    mode: "deep",
    time_range: "month",
    include_domains: ["docs.python.org", "python.org"],
  });
  for (const bad of [
    { time_range: "decade" },
    { include_domains: ["https://example.org/"] },
    { include_domains: ["127.0.0.1"] },
    { include_domains: ["example.local"] },
    { include_domains: ["example.org", "example.org"] },
    { include_domains: ["a.com", "b.com", "c.com", "d.com"] },
  ]) {
    assert.equal(parseResearchRequest({ question: "Latest findings", ...bad }), null);
  }
  assert.equal(parseResearchRequest({
    question: "Read this public webpage",
    mode: "url",
    source_url: "https://example.org",
    time_range: "week",
  }), null);
});
