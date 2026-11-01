import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import typescript from "typescript";

const source = readFileSync(new URL("../src/components/voice/browser-voice-mode.ts", import.meta.url), "utf8");
const compiled = typescript.transpileModule(source, {
  compilerOptions: { target: typescript.ScriptTarget.ES2022, module: typescript.ModuleKind.CommonJS },
}).outputText;

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
}
const tick = () => new Promise(resolve => setImmediate(resolve));
const response = body => ({ ok: true, json: async () => body });

function harness({ failRecognitionStart = false, cancelRaisesError = false, triggerNetworkTimeout = false } = {}) {
  const recognitions = [];
  const spoken = [];
  const pendingReplies = [];
  const errors = [];
  const transcribed = [];
  const audioEvents = [];
  let stopEvents = 0;
  const calls = [];

  class Recognition {
    startCount = 0;
    onresult = null;
    onend = null;
    onerror = null;
    start() {
      if (failRecognitionStart) throw new Error("permission refused");
      this.startCount++;
    }
    stop() { this.onend?.(); }
    abort() { this.onend?.(); }
    emitFinal(words) {
      this.onresult?.({
        resultIndex: 0,
        results: [{ 0: { transcript: words }, isFinal: true }],
      });
    }
    constructor() { recognitions.push(this); }
  }
  class Utterance {
    constructor(text) { this.text = text; }
  }
  const synthesis = {
    current: null,
    getVoices() {
      return [
        { lang: "en-US", name: "English" },
        { lang: "bn-BD", name: "Bengali native" },
        { lang: "ja-JP", name: "Japanese native" },
      ];
    },
    speak(utterance) {
      this.current = utterance;
      spoken.push(utterance);
    },
    cancel() {
      if (cancelRaisesError) this.current?.onerror?.({ error: "canceled" });
      this.current = null;
    },
  };
  const browser = {
    SpeechRecognition: Recognition,
    SpeechSynthesisUtterance: Utterance,
    speechSynthesis: synthesis,
  };
  const exports = {};
  const context = {
    exports,
    window: browser,
    navigator: { language: "en-US" },
    SpeechSynthesisUtterance: Utterance,
    AbortController,
    setTimeout: (callback, ms) =>
      triggerNetworkTimeout && ms === 75000
        ? setTimeout(callback, 0)
        : setTimeout(callback, ms),
    clearTimeout,
    fetch: (url, options) => {
      calls.push({ url, signal: options.signal });
      if (url === "/api/conversations") return Promise.resolve(response({ id: "conversation-1" }));
      const pending = deferred();
      pendingReplies.push(pending);
      options.signal.addEventListener("abort", () => {
        pending.reject(new Error("AbortError"));
      }, { once: true });
      return pending.promise;
    },
  };
  vm.runInNewContext(compiled, context, { timeout: 5000, filename: "browser-voice-mode.js" });
  const options = {
    mode: "normal",
    conversationId: null,
    documentIds: [],
    onState: () => {},
    onUserTranscript: () => {},
    onAgentTranscript: text => transcribed.push(text),
    onConversationStarted: () => {},
    onError: error => errors.push(error),
    onAudioBlocked: () => audioEvents.push("blocked"),
    onAudioStarted: () => audioEvents.push("started"),
    onStopped: () => { stopEvents++; },
  };
  return {
    api: exports, options, recognitions, pendingReplies, spoken,
    errors, transcribed, audioEvents, calls, synthesis,
    stopEvents: () => stopEvents,
    settle(reply = "Spoken answer") {
      assert.equal(pendingReplies.length, 1);
      pendingReplies[0].resolve(response({ assistant_message: { content: reply } }));
    },
  };
}

test("mute during network reply suppresses playback and serializes the turn", async () => {
  const h = harness();
  const controller = await h.api.startBrowserVoiceMode(h.options);
  assert.equal(h.recognitions[0].startCount, 1, "recognition starts on direct tap");
  await tick();
  h.recognitions[0].emitFinal("hello");
  await tick();
  assert.equal(h.pendingReplies.length, 1);
  controller.setMuted(true);
  controller.setMuted(false);
  assert.equal(h.recognitions[0].startCount, 1, "no second turn before reply completes");
  controller.setMuted(true);
  h.settle();
  await tick();
  assert.equal(h.spoken.length, 0, "muted reply must never play");
  assert.deepEqual(h.transcribed, ["Spoken answer"], "reply remains visible as text");
  assert.deepEqual(h.errors, []);
  controller.setMuted(false);
  await new Promise(resolve => setTimeout(resolve, 180));
  assert.ok(h.recognitions[0].startCount >= 2, "listening recovers after network turn");
  controller.stop();
  assert.equal(h.stopEvents(), 1);
});

test("normal reply plays once; cancel-on-mute is not presented as a playback failure", async () => {
  const h = harness({ cancelRaisesError: true });
  const controller = await h.api.startBrowserVoiceMode(h.options);
  await tick();
  h.recognitions[0].emitFinal("hello");
  await tick();
  h.settle();
  await tick();
  assert.equal(h.spoken.length, 1);
  controller.setMuted(true);
  assert.deepEqual(h.errors, [], "intentional cancellation must not raise user error");
  controller.stop();
  assert.equal(h.stopEvents(), 1);
});

test("hangup during a pending request aborts work and never plays stale audio", async () => {
  const h = harness();
  const controller = await h.api.startBrowserVoiceMode(h.options);
  await tick();
  h.recognitions[0].emitFinal("hello");
  await tick();
  const messageRequest = h.calls.find(x => x.url.endsWith("/messages"));
  assert.ok(messageRequest);
  controller.stop();
  assert.equal(messageRequest.signal.aborted, true);
  h.settle("stale answer");
  await tick();
  assert.equal(h.spoken.length, 0);
  assert.deepEqual(h.errors, []);
  controller.stop();
  assert.equal(h.stopEvents(), 1);
});

test("synchronous speech permission failure stops exactly once and reports the problem", async () => {
  const h = harness({ failRecognitionStart: true });
  const controller = await h.api.startBrowserVoiceMode(h.options);
  await tick();
  assert.equal(h.stopEvents(), 1);
  assert.match(h.errors[0], /microphone/i);
  controller.stop();
  assert.equal(h.stopEvents(), 1);
});

test("tap to hear replays last reply on user activation after Safari speech error", async () => {
  const h = harness();
  const controller = await h.api.startBrowserVoiceMode(h.options);
  await tick();
  assert.equal(controller.retryAudio(), false, "no reply exists yet");
  h.recognitions[0].emitFinal("hello");
  await tick();
  h.settle("Here is a test reply");
  await tick();
  assert.equal(h.spoken.length, 1);
  h.spoken[0].onerror?.({ error: "audio-busy" });
  assert.deepEqual(h.audioEvents, ["blocked"]);
  assert.equal(h.spoken.length, 1);
  assert.equal(controller.retryAudio(), true);
  assert.equal(h.spoken.length, 2);
  h.spoken[1].onstart?.();
  assert.deepEqual(h.audioEvents, ["blocked", "started"]);
  h.spoken[1].onend?.();
  assert.deepEqual(h.errors, ["Voice playback unavailable; the answer remains in chat."]);
  controller.stop();
});

test("muted/stopped browser calls cannot replay a reply even with audio unlock click", async () => {
  const h = harness();
  const controller = await h.api.startBrowserVoiceMode(h.options);
  await tick();
  h.recognitions[0].emitFinal("hello");
  await tick();
  h.settle();
  await tick();
  controller.setMuted(true);
  assert.equal(controller.retryAudio(), false);
  controller.stop();
  assert.equal(controller.retryAudio(), false);
  assert.equal(h.spoken.length, 1);
});

test("a stalled AI response hits a bounded deadline and resumes microphone listening", async () => {
  const h = harness({ triggerNetworkTimeout: true });
  const controller = await h.api.startBrowserVoiceMode(h.options);
  await tick();
  h.recognitions[0].emitFinal("hello");
  await new Promise(resolve => setTimeout(resolve, 190));
  assert.ok(h.errors.some(message => /timed out/.test(message)));
  assert.ok(h.recognitions[0].startCount >= 2, "listening must resume after timeout");
  assert.equal(h.spoken.length, 0);
  controller.stop();
});


test("a voice stop instruction does not create an unrelated AI reply", async () => {
  const h = harness();
  const controller = await h.api.startBrowserVoiceMode(h.options);
  await tick();
  h.recognitions[0].emitFinal("Stop speaking!");
  await tick();
  assert.equal(h.pendingReplies.length, 0);
  assert.equal(h.spoken.length, 0);
  controller.stop();
});

test("Stop reply immediately cancels browser TTS without ending the call", async () => {
  const h = harness({ cancelRaisesError: true });
  const controller = await h.api.startBrowserVoiceMode(h.options);
  await tick();
  h.recognitions[0].emitFinal("Tell me about you");
  await tick();
  h.settle("I'm Aqlyra, an AI assistant.");
  await tick();
  assert.equal(h.spoken.length, 1);
  assert.equal(controller.interruptSpeech(), true);
  assert.equal(h.synthesis.current, null);
  assert.equal(h.stopEvents(), 0, "stopping speech must not hang up");
  assert.equal(controller.interruptSpeech(), false);
  assert.deepEqual(h.errors, []);
  controller.stop();
});

test("language selector applies to recognition and TTS picks same-language native voices", async () => {
  const h = harness();
  const controller = await h.api.startBrowserVoiceMode(h.options);
  await tick();
  controller.setSpeechLocale("bn-BD");
  assert.equal(h.recognitions[0].lang, "bn-BD");
  // The locale switch can restart the microphone asynchronously.
  h.recognitions[0].emitFinal("বাংলায় কথা বলো");
  await tick();
  h.settle("আমি বাংলায় উত্তর দিচ্ছি।");
  await tick();
  assert.equal(h.spoken.length, 1);
  assert.equal(h.spoken[0].lang, "bn-BD");
  assert.equal(h.spoken[0].voice?.lang, "bn-BD");
  assert.ok(h.spoken[0].rate < 1);
  controller.stop();
});

test("late microphone echo cannot trigger a second AI turn", async () => {
  const h = harness();
  const controller = await h.api.startBrowserVoiceMode(h.options);
  await tick();
  h.recognitions[0].emitFinal("Hello");
  await tick();
  h.settle("An informative answer spoken by the assistant.");
  await tick();
  h.spoken[0].onstart?.();
  h.spoken[0].onend?.();
  await new Promise(resolve => setTimeout(resolve, 820));
  h.recognitions[0].emitFinal("informative answer spoken by the assistant");
  await tick();
  assert.equal(h.pendingReplies.length, 1, "speaker echo should be ignored");
  controller.stop();
});
