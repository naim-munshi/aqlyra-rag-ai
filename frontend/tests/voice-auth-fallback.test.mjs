import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const voice = readFileSync(
  new URL("../src/components/voice/voice-call-button.tsx", import.meta.url),
  "utf8",
);

test("logged-out voice status rejects browser fallback before microphone activation", () => {
  assert.match(voice, /response\.status === 401/);
  assert.match(voice, /requiresAuth: true/);
  assert.match(voice, /Sign in to use voice calls/);
  const gate = voice.indexOf("if (availability?.requiresAuth)");
  const fallback = voice.indexOf("availability?.available === false && browserSpeechIsSupported()", gate);
  assert.ok(gate > 0 && fallback > gate, "auth gate must precede speech fallback");
  assert.match(voice, /void fetch\("\/api\/voice\/status"/);
  assert.match(voice, /refreshVoiceAvailability\(\)/);
});

test("sync microphone startup failures invalidate pending async controller", () => {
  assert.match(voice, /if \(callAttemptRef\.current === attempt\) callAttemptRef\.current \+= 1/);
  assert.match(voice, /if \(callAttemptRef\.current !== attempt\) \{\s*controller\.stop\(\);\s*return;/);
});

test("LiveKit direct-gesture capture and timeout fail-closed remain intact", () => {
  assert.match(voice, /await createLocalAudioTrack\(\{/);
  assert.match(voice, /await room\.localParticipant\.publishTrack\(microphoneTrack/);
  assert.match(voice, /const timeoutId = setTimeout\(\(\) => requestController\.abort\(\), 15000\)/);
  assert.match(voice, /room\.startAudio\(\)/);
  assert.match(voice, /The AI voice agent did not join/);
});

test("a missing LiveKit worker does not trap users in endless real-time retries", () => {
  assert.match(voice, /preferBrowserSpeechRef = useRef\(false\)/);
  assert.match(voice, /preferBrowserSpeechRef\.current = hasBrowserFallback/);
  assert.match(voice, /Tap the microphone again to use Browser Voice/);
  assert.match(voice, /preferBrowserSpeechRef\.current && browserSpeechIsSupported\(\)/);
  assert.match(voice, /&& !availability\?\.requiresAuth/);
  assert.match(voice, /void startBrowserSpeech\(\)/);
});
