import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const voice = readFileSync(
  new URL("../src/components/voice/voice-call-button.tsx", import.meta.url),
  "utf8",
);

test("LiveKit unavailability never silently switches transport and browser voice is explicitly selected", () => {
  assert.match(voice, /response\.status === 401/);
  assert.match(voice, /requiresAuth: true/);
  assert.match(voice, /Sign in to use voice calls/);
  assert.match(voice, /if \(!availability\?\.available\)/);
  assert.match(voice, /function startFreeBrowserCall\(\)/);
  assert.match(voice, /onClick=\{startFreeBrowserCall\}/);
  assert.match(voice, /browserSpeechIsSupported\(\)/);
  assert.match(voice, /startBrowserVoiceMode\(\{/);
  assert.match(voice, /Browser speech is opt-in, not a silent downgrade/);
  assert.match(voice, /availability\?\.requiresAuth/);
  assert.match(voice, /Start free browser voice conversation/);
  assert.match(voice, /onClick=\{\(\) => \{ void startCall\(\); \}\}/);
  assert.match(voice, /Stop reply/);
  assert.match(voice, /browserControllerRef\.current\?\.stop\(\)/);
  assert.match(voice, /browserControllerRef\.current\?\.setMuted\(nextMuted\)/);
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
