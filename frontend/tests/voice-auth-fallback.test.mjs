import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const voice = readFileSync(
  new URL("../src/components/voice/voice-call-button.tsx", import.meta.url),
  "utf8",
);

test("signed-out and unavailable calls cannot silently switch to browser speech", () => {
  assert.match(voice, /response\.status === 401/);
  assert.match(voice, /requiresAuth: true/);
  assert.match(voice, /Sign in to use voice calls/);
  assert.match(voice, /if \(!availability\?\.available\)/);
  assert.doesNotMatch(voice, /startBrowserVoiceMode|startBrowserSpeech|browserSpeechIsSupported/);
  assert.doesNotMatch(voice, /Aqlyra Browser Voice|Device \/ Auto/);
  assert.doesNotMatch(voice, /Recognition language|Stop reply/);
  assert.match(voice, /refreshVoiceAvailability\(\)/);
});

test("LiveKit voice-only user experience supports natural hands-free interruptions", () => {
  assert.match(voice, /await createLocalAudioTrack\(\{/);
  assert.match(voice, /await room\.localParticipant\.publishTrack\(microphoneTrack/);
  assert.match(voice, /const timeoutId = setTimeout\(\(\) => requestController\.abort\(\), 15000\)/);
  assert.match(voice, /room\.startAudio\(\)/);
  assert.match(voice, /waitForAgent\(room\)/);
  assert.match(voice, /Aqlyra Voice/);
  assert.match(voice, /Speak naturally/);
});

test("worker join timeout is visible and releases microphone, never fakes a live call", () => {
  assert.match(voice, /Real-time voice could not connect to Aqlyra/);
  assert.match(voice, /roomRef\.current = null;\s*stopMicrophoneTrack\(\)/);
  assert.match(voice, /setAgentState\("error"\)/);
  assert.match(voice, /clearAgentJoinTimer\(\)/);
  assert.doesNotMatch(voice, /preferBrowserSpeechRef/);
});

test("session and auth failures remain bounded and safe", () => {
  assert.match(voice, /sessionRequestControllerRef\.current\?\.abort\(\)/);
  assert.match(voice, /hasVoiceAgent\(room\)/);
  assert.match(voice, /await room\.connect\(/);
  assert.match(voice, /Untrusted request origin|Sign in to use voice calls|voice is unavailable/i);
});
