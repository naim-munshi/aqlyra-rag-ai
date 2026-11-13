# Browser voice fallback (Voice Call feature)

Aqlyra first attempts the existing LiveKit realtime voice session. When the
authenticated backend returns HTTP 503 (voice service unavailable) **and**
the user agent implements Web Speech recognition and speech synthesis, the
voice button offers a second **explicit** choice: "Use browser voice".

This is a sequential speech-to-text -> authenticated normal/knowledge chat ->
text-to-speech mode, **not a LiveKit/WebRTC call**. It does not fake a LiveKit
room or use unapproved third-party API keys. It uses the same owner-bound
conversation/message APIs as typing, so the chat history is preserved and
cross-account access checks remain in place.

Privacy and access:
- Microphone starts only after the user clicks the browser-voice consent
  action. Depending on the browser, transcription may be processed by the
  browser vendor. The UI explicitly discloses that before activation.
- Requires an authenticated conversation. New conversations are created with
  the existing authenticated API; no unauthenticated guest voice calls.
- Recognizer language can be selected as Bengali, Japanese, English, or
  device default. Browser recognition/voice availability varies by OS and
  installed language packs; speaking Bangla does not guarantee Bangla output.
- User can mute or stop; stop cancels current browser speech and in-flight
  fetch. No raw audio is stored in Aqlyra's backend.
- If browser recognition is unsupported or microphone permission is denied,
  the user gets an explicit error and can continue text chat.
- It does not enable LiveKit room dispatch, low latency barge-in, realtime
  interruption handling, server-side VAD, or full voice-call parity.

Acceptance: ESLint, TypeScript, frontend build and node browser-stub tests
must pass. Real iPhone Safari, Chrome, permission, recognition and speech
synthesis tests remain required before universal-support claims.

LiveKit remains gated by LiveKit account credentials, active RTC worker,
Groq STT and an available multilingual TTS provider, with physical-device
end-to-end acceptance. Do not set VOICE_AGENT_READY=true from the existence
of the browser-only fallback.
