# Aqlyra Voice — free-tier setup and safety

## Provider choice

- **LiveKit Cloud Build (free):** https://cloud.livekit.io and https://livekit.com/pricing . The free plan currently includes $2.50 in monthly inference credits and 1,000 agent-session minutes. Credits are consumed by Deepgram Nova-3 and Cartesia Sonic 3; free quotas stop requests when exhausted. No credit card is required to start.
- **GroqCloud Free:** https://console.groq.com/keys and https://console.groq.com/docs/rate-limits . Use openai/gpt-oss-20b as Aqlyra's existing chat/RAG brain, subject to the account's Free rate limits. No paid OpenAI key is required in this **particular** configuration.
- **Embedding model:** Match the backend's actual existing provider, credentials, model and 384-dimensional pgvector index. Do not invent a new embedding model for a live database; voice RAG and memory require compatible embeddings.
- **Hosting:** Railway worker compute/billing is separate from free LiveKit/Groq API quotas. No Railway infrastructure was deployed by preparing this configuration.

## Already staged for Railway voice worker (not deployed)

VOICE_STT_PROVIDER=livekit
VOICE_STT_MODEL=deepgram/nova-3
VOICE_STT_LANGUAGE=multi
VOICE_SESSION_LLM_PROVIDER=livekit
VOICE_SESSION_LLM_MODEL=openai/gpt-oss-120b
VOICE_TTS_MODEL=cartesia/sonic-3
LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-20b
VOICE_AGENT_READY=false

The LiveKit session LLM is SDK plumbing; actual answers still go through Aqlyra's existing execute_chat_turn, knowledge retrieval, memory, scopes and persistence. Direct Groq STT is not used in this setup. The Groq key powers the existing Aqlyra chat brain.

## Keys the account owner must create, privately

1. LiveKit Cloud → Project → Settings → Keys: generate LIVEKIT_API_KEY and LIVEKIT_API_SECRET, and copy the corresponding wss LIVEKIT_URL. Keep the project on Build.
2. GroqCloud → API Keys: create GROQ_API_KEY under the Free plan.
3. Enter those values in the Railway staging voice-worker Variables panel, not in GitHub or this chat. The worker also needs its intended backend's matching SECRET_KEY, DATABASE_URL, REDIS_URL and compatible embedding provider credential.
4. Do not commit the existing full Railway staging patch. It contains unrelated services and storage changes. Apply only after isolating and approving the voice worker resource and any necessary test dependencies.

## Keyless voice alternative

The existing frontend browser voice fallback uses native SpeechRecognition and speechSynthesis to call the authenticated conversation backend. It needs no LiveKit key for audio, but requires browser support and a working existing chat provider. It is not equivalent to LiveKit WebRTC, and still needs real iOS/Android acceptance.

## Release criteria

Verify no paid plan is enabled. Confirm LiveKit agent registration, real multilingual audio, usage quotas, account authorization/revocation, real backend LLM+embeddings, and test-device success. Until then do not enable production VOICE_AGENT_READY or claim live calls work.