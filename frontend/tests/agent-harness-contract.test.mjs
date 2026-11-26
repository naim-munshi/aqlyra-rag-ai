import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const workspace = readFileSync(
  new URL("../src/components/chat/rag-workspace.tsx", import.meta.url),
  "utf8",
);
const researchRoute = readFileSync(
  new URL("../src/app/api/agent-harness/research/route.ts", import.meta.url),
  "utf8",
);
const runsRoute = readFileSync(
  new URL("../src/app/api/agent-harness/runs/route.ts", import.meta.url),
  "utf8",
);
const detailRoute = readFileSync(
  new URL("../src/app/api/agent-harness/runs/[runId]/route.ts", import.meta.url),
  "utf8",
);
const usageRoute = readFileSync(
  new URL("../src/app/api/agent-harness/usage/route.ts", import.meta.url),
  "utf8",
);
const tracePage = readFileSync(
  new URL("../src/app/agent-harness/page.tsx", import.meta.url),
  "utf8",
);

test("research agent is opt-in and only exposed in Knowledge mode", () => {
  assert.match(workspace, /useState\(false\);/);
  assert.match(workspace, /chatMode === "knowledge" && \(/);
  assert.match(workspace, /Research Agent<\/span>/);
  assert.match(workspace, /researchAgentEnabled \? "On" : "Off"/);
  assert.match(workspace, /if \(researchAgentEnabled\)/);
  assert.match(workspace, /setResearchAgentEnabled\(false\)/);
});

test("agent BFF requires trusted same-origin POST and a valid session", () => {
  assert.match(researchRoute, /hasTrustedRequestOrigin\(request\)/);
  assert.match(researchRoute, /getAccessToken\(\)/);
  assert.match(researchRoute, /readBoundedJson\(request, 16_384\)/);
  assert.match(researchRoute, /privateJsonResponse\(/);
  assert.match(researchRoute, /cache: "no-store"/);
  assert.match(researchRoute, /backendUrl\("\/agent-harness\/research"\)/);
});

test("trace BFF endpoints are authenticated, private and no-store", () => {
  for (const source of [runsRoute, detailRoute]) {
    assert.match(source, /getAccessToken\(\)/);
    assert.match(source, /privateJsonResponse\(/);
    assert.match(source, /cache: "no-store"/);
    assert.match(source, /Authorization:/);
    assert.match(source, /accessToken/);
  }
  assert.match(detailRoute, /encodeURIComponent\(runId\)/);
});

test("trace viewer surfaces owner trace summaries and individual execution steps", () => {
  assert.match(tracePage, /Research agent traces/);
  assert.match(tracePage, /Estimated cost/);
  assert.match(tracePage, /Execution timeline/);
  assert.match(tracePage, /selected\.steps\.map/);
  assert.match(tracePage, /Only your own traces are shown/);
  assert.match(tracePage, /Daily agent spend/);
  assert.match(tracePage, /Embedding.*not itemized/);
  assert.match(usageRoute, /getAccessToken\(\)/);
  assert.match(usageRoute, /privateJsonResponse\(/);
  assert.match(usageRoute, /agent-harness\/usage/);
});
