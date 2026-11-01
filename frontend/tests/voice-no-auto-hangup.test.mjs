import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";

const read = path => readFileSync(new URL("../src/" + path, import.meta.url), "utf8");

test("first voice transcript cannot unmount the LiveKit call when chat layout changes", () => {
  const source = read("components/chat/rag-workspace.tsx");
  const tree = ts.createSourceFile("rag-workspace.tsx", source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const composerCalls = [];
  const layoutConditions = [];
  function visit(node) {
    if (ts.isCallExpression(node) && node.expression.getText(tree) === "renderComposer") {
      composerCalls.push(node);
    }
    if (ts.isConditionalExpression(node) && node.condition.getText(tree) === "!hasConversation") {
      layoutConditions.push(node);
    }
    ts.forEachChild(node, visit);
  }
  visit(tree);
  assert.equal(composerCalls.length, 1, "The composer must have a single persistent React identity");
  assert.equal(layoutConditions.length, 1, "The welcome / history layout must still switch");
  const composer = composerCalls[0];
  const layout = layoutConditions[0];
  assert.ok(
    composer.getStart(tree) > layout.getEnd(),
    "The mounted voice component must be a sibling after the layout conditional, not inside either branch",
  );
  assert.match(source, /<VoiceCallButton/);
  assert.match(source, /void refreshVoiceConversation\(/);
  assert.match(source, /setTurns\(\s*turnsFromPersistedMessages/);
});

test("a WebRTC disconnect is visible rather than silently resetting to idle", () => {
  const voice = read("components/voice/voice-call-button.tsx");
  const handler = voice.slice(voice.indexOf("RoomEvent.Disconnected"));
  assert.ok(handler.length > 100);
  assert.match(handler, /if \(roomRef\.current !== room\) return/);
  assert.match(handler, /agentEverJoinedRef\.current/);
  assert.match(handler, /setAgentState\("error"\)/);
  assert.match(handler, /setError\(message\)/);
  assert.match(handler, /onError\?\.\(message\)/);
  assert.match(voice, /roomRef\.current = null;[\s\S]*?void room\.disconnect\(\)/);
});

test("429 voice session limit gives Retry-After and cannot create a retry loop", () => {
  const voice = read("components/voice/voice-call-button.tsx");
  assert.match(voice, /response\.status === 429/);
  assert.match(voice, /response\.headers\.get\("Retry-After"\)/);
  assert.match(voice, /Too many voice reconnect attempts/);
  assert.doesNotMatch(voice, /setInterval\(/);
});
