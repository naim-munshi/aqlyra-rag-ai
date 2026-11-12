import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = path => readFileSync(new URL("../src/" + path, import.meta.url), "utf8");

test("iPhone keyboard focus cannot autozoom the Aqlyra composer", () => {
  const source = read("components/chat/rag-workspace.tsx");
  assert.match(source, /rows=\{1\}/);
  assert.match(source, /ref=\{composerTextareaRef\}/);
  assert.match(source, /text-base leading-6[^"]*sm:text-sm/);
  assert.match(source, /aria-label="Message Aqlyra"/);
  assert.match(source, /enterKeyHint="send"/);
  assert.match(source, /Math\.min\(112, Math\.max\(24, textarea\.scrollHeight\)\)/);
  assert.match(source, /\}, \[question\]\)/);
  assert.match(source, /className="mt-2 flex[^"]*sm:mt-3/);
  assert.doesNotMatch(source, /<textarea\s*rows=\{2\}/);
});

test("mobile send control stays compact and accessible while retaining desktop label", () => {
  const source = read("components/chat/rag-workspace.tsx");
  assert.match(source, /aria-label="Send message"/);
  assert.match(source, /min-w-10[^"]*justify-center[^"]*rounded-full[^"]*sm:rounded-xl/);
  assert.match(source, /<span className="hidden sm:inline">Send<\/span>/);
  assert.match(source, /\!question\.trim\(\) &&\s*\!attachedDocument/);
});

test("Free Voice stays one tap, with LiveKit only in an accessible secondary menu", () => {
  const source = read("components/voice/voice-call-button.tsx");
  assert.match(source, /onClick=\{startFreeBrowserCall\}/);
  assert.match(source, /aria-label="More voice options"/);
  assert.match(source, /aria-expanded=\{voiceOptionsOpen\}/);
  assert.match(source, /aria-haspopup="menu"/);
  assert.match(source, /role="menu"/);
  assert.match(source, /aria-label="Start LiveKit real-time voice"/);
  assert.match(source, /onClick=\{\(\) => \{ void startCall\(\); \}\}/);
  assert.match(source, /dismissOutside/);
  assert.match(source, /dismissEscape/);
  assert.doesNotMatch(source, />\s*LiveKit\s*<\/button>/);
});

test("composer remains mounted when welcome screen transitions into chat", () => {
  const source = read("components/chat/rag-workspace.tsx");
  assert.match(source, /\{renderComposer\(\s*!hasConversation/);
  assert.equal((source.match(/\{renderComposer\(/g) || []).length, 1);
  assert.match(source, /<VoiceCallButton/);
  assert.match(source, /pb-\[max\(0\.5rem,env\(safe-area-inset-bottom\)\)\]/);
});
