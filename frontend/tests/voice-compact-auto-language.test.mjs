import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = relative => readFileSync(new URL("../src/" + relative, import.meta.url), "utf8");
const voice = read("components/voice/voice-call-button.tsx");
const orb = read("components/voice/voice-orb.tsx");
const browser = read("components/voice/browser-voice-mode.ts");

test("mobile voice panel stays compact and accessible", () => {
  assert.match(voice, /w-\[min\(296px,calc\(100vw-24px\)\)\]/);
  assert.match(voice, /bottom-\[60px\]/);
  assert.match(voice, /aria-label="Voice conversation"/);
  assert.match(voice, /<VoiceOrb\s+compact/);
  assert.match(orb, /compact \? "h-12 w-12" : "h-24 w-24"/);
  assert.match(voice, /aria-label="End voice conversation"/);
  assert.match(voice, /aria-label=\{muted \? "Unmute microphone" : "Mute microphone"\}/);
  assert.match(voice, /Stop reply/);
  assert.match(voice, /aria-live="polite"/);
});

test("voice never exposes technical mode or manual language controls", () => {
  assert.doesNotMatch(voice, /id="browser-voice-locale"/);
  assert.doesNotMatch(voice, /<select/);
  assert.doesNotMatch(voice, /Listen in/);
  assert.doesNotMatch(voice, /Aqlyra · Free Browser Voice/);
  assert.doesNotMatch(voice, /LiveKit\s*<\/button>/);
  assert.doesNotMatch(voice, /speechLocale|setSpeechLocale/);
  assert.doesNotMatch(browser, /setSpeechLocale|options\.speechLocale/);
  assert.match(voice, /Aqlyra Voice/);
});

test("speech disclosure stays available without occupying permanent space", () => {
  assert.match(voice, /<details className=/);
  assert.match(voice, /About voice privacy/);
  assert.match(voice, /Speech recognition may be processed by your browser provider/);
  assert.match(voice, /Normal Aqlyra AI chat limits still apply/);
});

test("input locale adapts only after transcript; AI reply determines TTS locale", () => {
  assert.match(browser, /recognition\.lang = navigator\.language \|\| "en-US"/);
  assert.match(browser, /recognition\.lang = speechLanguage\(text\)/);
  assert.match(browser, /utterance\.lang = speechLanguage\(content\)/);
  assert.match(browser, /speechLanguage\(text: string\)/);
  assert.doesNotMatch(browser, /automatic audio language identification|audio-first language detection enabled/i);
});
