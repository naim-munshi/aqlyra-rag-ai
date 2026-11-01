import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";

const source = readFileSync(
  new URL("../src/components/chat/rag-workspace.tsx", import.meta.url),
  "utf8",
);
const ast = ts.createSourceFile(
  "rag-workspace.tsx",
  source,
  ts.ScriptTarget.Latest,
  true,
  ts.ScriptKind.TSX,
);

test("new-chat welcome and composer are vertically centered without absolute positioning", () => {
  assert.match(
    source,
    /flex min-h-0 min-w-0 flex-1 items-end justify-center px-3 pb-4 sm:px-6 sm:pb-5/,
    "the welcome copy should rest above the centered composer",
  );
  assert.match(
    source,
    /!hasConversation && \(\s*<div aria-hidden="true" className="min-h-0 flex-1" \/>/,
    "matching lower flexible space should center the welcome/input group",
  );
  assert.match(
    source,
    /hasConversation\s*\? "px-2 pb-\[max\(0\.5rem,env\(safe-area-inset-bottom\)\)\] pt-2 sm:px-5 sm:pb-5"/,
    "existing conversations still pin the input to the bottom safe-area",
  );
  assert.match(
    source,
    /: "px-3 pb-2 pt-1 sm:px-6 sm:pb-3"/,
    "new chat uses compact, responsive spacing",
  );
});

test("moving the input does not remount the active LiveKit voice call", () => {
  const composerCalls = [];
  const welcomeConditions = [];
  function visit(node) {
    if (
      ts.isCallExpression(node) &&
      node.expression.getText(ast) === "renderComposer"
    ) composerCalls.push(node);
    if (
      ts.isConditionalExpression(node) &&
      node.condition.getText(ast) === "!hasConversation"
    ) welcomeConditions.push(node);
    ts.forEachChild(node, visit);
  }
  visit(ast);
  assert.equal(composerCalls.length, 1);
  assert.equal(welcomeConditions.length, 1);
  assert.ok(composerCalls[0].getStart(ast) > welcomeConditions[0].getEnd());
  assert.equal((source.match(/<VoiceCallButton\b/g) || []).length, 1);
  assert.match(source, /renderComposer\(\s*!hasConversation,?\s*\)/);
});

test("chat-mode, Send and voice controls stay available in both layouts", () => {
  assert.match(source, /mode=\{chatMode\}/);
  assert.match(source, /onSubmit=\{handleSubmit\}/);
  assert.match(source, /aria-label="Start voice conversation"|<VoiceCallButton/);
  assert.match(source, /\{chatMode === "normal"/);
  assert.match(source, /Send\s*<\/button>/);
});
