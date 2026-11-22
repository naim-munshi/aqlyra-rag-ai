import assert from "node:assert/strict";
import test from "node:test";

import {
  browserSpeechIsSupported,
  startBrowserVoiceMode,
} from "../src/components/voice/browser-voice-mode.ts";

test("browser voice opt-in sends finalized transcript to owned chat and handles playback", async () => {
  const originalWindow = globalThis.window;
  const originalUtterance = globalThis.SpeechSynthesisUtterance;
  const originalFetch = globalThis.fetch;
  const calls = [];
  let microphone = null;
  let spoken = "";
  let stopped = 0;

  class Recognition {
    start() { microphone = { lang: this.lang, onresult: (event) => this.onresult?.(event) }; }
    stop() {}
    abort() { stopped += 1; }
  }
  class Utterance {
    constructor(text) { this.text = text; }
  }
  globalThis.window = {
    SpeechRecognition: Recognition,
    SpeechSynthesisUtterance: Utterance,
    speechSynthesis: {
      speak(utterance) {
        spoken = utterance.text;
        utterance.onend?.();
      },
      cancel() {},
    },
  };
  globalThis.SpeechSynthesisUtterance = Utterance;
  globalThis.fetch = async (url, options) => {
    calls.push({ url, body: JSON.parse(options.body) });
    if (url === "/api/conversations") {
      return { ok: true, json: async () => ({ id: "owned-conversation" }) };
    }
    return {
      ok: true,
      json: async () => ({
        assistant_message: { content: "Answer grounded in current chat." },
      }),
    };
  };
  const transcripts = [];
  try {
    assert.equal(browserSpeechIsSupported(), true);
    const handle = await startBrowserVoiceMode({
      mode: "normal",
      conversationId: null,
      documentIds: [],
      speechLocale: "bn-BD",
      onConversationStarted(id) { assert.equal(id, "owned-conversation"); },
      onUserTranscript(text, final) {
        if (final) transcripts.push(text);
      },
      onAgentTranscript(text, final) {
        if (final) transcripts.push(text);
      },
      onState() {},
      onError(reason) { throw new Error(reason); },
      onStopped() {},
    });
    await new Promise(resolve => setTimeout(resolve, 200));
    assert.equal(microphone?.lang, "bn-BD");
    microphone.onresult({
      resultIndex: 0,
      results: [{ isFinal: true, 0: { transcript: "আমার কথা বলো" } }],
    });
    await new Promise(resolve => setTimeout(resolve, 40));
    assert.deepEqual(calls.map(call => call.url), [
      "/api/conversations",
      "/api/conversations/owned-conversation/messages",
    ]);
    assert.equal(calls[1].body.content, "আমার কথা বলো");
    assert.equal(spoken, "Answer grounded in current chat.");
    assert.deepEqual(transcripts, [
      "আমার কথা বলো", "Answer grounded in current chat.",
    ]);
    handle.stop();
    assert.ok(stopped >= 1);
  } finally {
    globalThis.window = originalWindow;
    globalThis.SpeechSynthesisUtterance = originalUtterance;
    globalThis.fetch = originalFetch;
  }
});

test("unsupported browser speech does not start a microphone", () => {
  const originalWindow = globalThis.window;
  try {
    globalThis.window = {};
    assert.equal(browserSpeechIsSupported(), false);
  } finally {
    globalThis.window = originalWindow;
  }
});
