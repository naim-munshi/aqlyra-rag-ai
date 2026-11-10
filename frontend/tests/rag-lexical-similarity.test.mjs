import test from "node:test";
import assert from "node:assert/strict";
import { formatSimilarity } from "../src/lib/format-similarity.ts";

test("lexical-only citation never presents internal zero as dense similarity", () => {
  assert.equal(formatSimilarity(null), "Lexical only");
});

test("real dense similarity values remain distinguishable, including measured zero", () => {
  assert.equal(formatSimilarity(0), "0.000");
  assert.equal(formatSimilarity(0.42), "0.420");
  assert.equal(formatSimilarity(0.91), "0.910");
});

test("malformed unavailable numeric response does not render NaN/Infinity", () => {
  assert.equal(formatSimilarity(Number.NaN), "Unavailable");
  assert.equal(formatSimilarity(Number.POSITIVE_INFINITY), "Unavailable");
});
