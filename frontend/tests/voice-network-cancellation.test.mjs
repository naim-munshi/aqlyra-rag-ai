import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const voice = readFileSync(new URL("../src/components/voice/voice-call-button.tsx", import.meta.url), "utf8");

test("voice request is cancellable by hangup and unmount", () => {
  assert.match(voice, /const sessionRequestControllerRef = useRef<AbortController \| null>\(null\)/);
  assert.match(voice, /sessionRequestControllerRef\.current\?\.abort\(\)/);
  assert.match(voice, /signal: requestController\.signal/);
  assert.match(voice, /callAttemptRef\.current \+= 1/);
});

test("network timeout cannot hold microphone and stale calls never reactivate", () => {
  assert.match(voice, /setTimeout\(\(\) => requestController\.abort\(\), 15000\)/);
  assert.match(voice, /clearTimeout\(timeoutId\)/);
  assert.match(voice, /microphoneTrack\.stop\(\)/);
  assert.match(voice, /callAttemptRef\.current !== attempt/);
  assert.match(voice, /startingRef\.current = true/);
  assert.match(voice, /startingRef\.current = false/);
});

test("unavailable worker can be rechecked without soliciting microphone permissions", () => {
  assert.match(voice, /refreshVoiceAvailability\(\)/);
  assert.match(voice, /Check voice availability again/);
  assert.match(voice, /if \(!availability\?\.available\)/);
});
