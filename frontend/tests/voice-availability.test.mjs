import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = path => readFileSync(new URL("../src/" + path, import.meta.url), "utf8");

test("unavailable voice calls show user-visible error and cannot request microphone", () => {
  const source = read("components/voice/voice-call-button.tsx");
  assert.match(source, /availability\?\.available/);
  assert.match(source, /if \(!availability\?\.available\)/);
  assert.match(source, /role="alert"/);
  assert.match(source, /Checking voice availability/);
  assert.match(source, /navigator\.mediaDevices\?\.getUserMedia/);
});

test("Safari microphone and sound need direct user actions", () => {
  const source = read("components/voice/voice-call-button.tsx");
  assert.match(source, /createLocalAudioTrack\(\{/);
  assert.match(source, /room\.localParticipant\.publishTrack\(microphoneTrack/);
  assert.doesNotMatch(source, /getTracks\(\)\.forEach\(track => track\.stop\(\)\)/);
  assert.match(source, /stopMicrophoneTrack\(\)/);
  assert.match(source, /callAttemptRef\.current !== attempt/);
  assert.match(source, /case "connecting":\s*return "Connecting";/);
  assert.doesNotMatch(source, /case "connecting":\s*return "Connecting";\s*case "connecting":/);
  assert.match(source, /RoomEvent\.AudioPlaybackStatusChanged/);
  assert.match(source, /await room\.startAudio\(\)/);
  assert.match(source, /Enable sound/);
  assert.match(source, /Microphone access was denied/);
});

test("voice agent timeout ends abandoned call and mobile sheet fits viewport", () => {
  const source = read("components/voice/voice-call-button.tsx");
  assert.match(source, /The AI voice agent did not join/);
  assert.match(source, /void room\.disconnect\(\)/);
  assert.match(source, /w-\[min\(300px,calc\(100vw-24px\)\)\]/);
});

test("private no-store voice preflight endpoint is separate from token issuance", () => {
  const source = read("app/api/voice/status/route.ts");
  assert.match(source, /getAccessToken\(\)/);
  assert.match(source, /backendUrl\("\/voice\/status"\)/);
  assert.match(source, /private, no-store/);
  assert.doesNotMatch(source, /participant_token/);
});
