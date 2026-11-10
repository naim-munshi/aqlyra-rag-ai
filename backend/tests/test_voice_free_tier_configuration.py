"""Offline free-plan recipe: LiveKit speech + Groq free-tier brain.

No live credentials are generated or transmitted. The runtime must still
check quotas and provider readiness before enabling real voice sessions.
"""
import pytest

from app.voice.preflight import (
    VoiceWorkerPreflightError,
    validate_voice_worker_environment,
)
from test_voice_worker_preflight import valid_env


def free_tier_voice_env():
    env = valid_env()
    env.update(
        VOICE_STT_PROVIDER="livekit",
        VOICE_STT_MODEL="deepgram/nova-3",
        VOICE_STT_LANGUAGE="multi",
        VOICE_SESSION_LLM_PROVIDER="livekit",
        VOICE_SESSION_LLM_MODEL="openai/gpt-oss-120b",
        VOICE_TTS_MODEL="cartesia/sonic-3",
        LLM_PROVIDER="groq",
        LLM_MODEL="openai/gpt-oss-20b",
        GROQ_API_KEY="synthetic-test-only-value",
        OPENAI_API_KEY="",
    )
    return env


def test_free_livekit_and_groq_brain_do_not_require_paid_openai_key():
    validate_voice_worker_environment(free_tier_voice_env())


def test_free_groq_brain_missing_key_fails_closed():
    env = free_tier_voice_env()
    env["GROQ_API_KEY"] = ""
    with pytest.raises(VoiceWorkerPreflightError, match="GROQ_API_KEY"):
        validate_voice_worker_environment(env)


@pytest.mark.parametrize("key", [
    "LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET",
])
def test_free_plan_does_not_mean_anonymous_livekit_credentials(key):
    env = free_tier_voice_env()
    env[key] = ""
    with pytest.raises(VoiceWorkerPreflightError, match=key):
        validate_voice_worker_environment(env)
