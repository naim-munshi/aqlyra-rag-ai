"""Offline worker boot gates; does not call LiveKit/Groq or use live secrets."""
import pytest
from app.voice.preflight import (
    REQUIRED, VoiceWorkerPreflightError, validate_voice_worker_environment,
)


def valid_env():
    return {
        "APP_ENV": "production",
        "AQLYRA_PROCESS_ROLE": "voice_worker",
        "RATE_LIMIT_ENABLED": "true",
        "RAG_GROUNDING_VERIFIER_ENABLED": "true",
        "LLM_PROVIDER": "groq",
        "EMBEDDING_PROVIDER": "huggingface",
        "HF_TOKEN": "test-only-placeholder-hf",
        "SECRET_KEY": "s" * 48,
        "DATABASE_URL": "postgresql+psycopg://user:fake@db.example.com:5432/voice",
        "REDIS_URL": "rediss://redis.example.com:6380",
        "LIVEKIT_URL": "wss://example.livekit.cloud",
        "LIVEKIT_API_KEY": "test-non-production-key",
        "LIVEKIT_API_SECRET": "s" * 42,
        "VOICE_AGENT_NAME": "aqlyra-voice",
        "GROQ_API_KEY": "test-placeholder-key",
        "VOICE_STT_PROVIDER": "livekit",
        "VOICE_STT_MODEL": "deepgram/nova-3",
        "VOICE_STT_LANGUAGE": "multi",
        "VOICE_SESSION_LLM_PROVIDER": "livekit",
        "VOICE_SESSION_LLM_MODEL": "openai/gpt-oss-120b",
        "VOICE_TTS_MODEL": "cartesia/sonic-3",
        "VOICE_TTS_VOICE": "fake-voice",
    }


def test_all_configured_passes_offline():
    validate_voice_worker_environment(valid_env())


@pytest.mark.parametrize("key", REQUIRED)
def test_missing_required_key_blocks_start_and_never_discloses_value(key):
    data = valid_env()
    data[key] = ""
    with pytest.raises(VoiceWorkerPreflightError) as exc:
        validate_voice_worker_environment(data)
    assert key in str(exc.value)
    assert "test-non-production-key" not in str(exc.value)


@pytest.mark.parametrize("url", [
    "ws://example.livekit.cloud", "wss://127.0.0.1", "wss://localhost",
    "wss://169.254.169.254", "wss://private.internal",
    "wss://user:pass@example.livekit.cloud", "wss://example.livekit.cloud?token=secret",
    "wss://example.livekit.cloud/path", "not-a-url",
])
def test_insecure_livekit_endpoint_blocks_worker(url):
    data = valid_env()
    data["LIVEKIT_URL"] = url
    with pytest.raises(VoiceWorkerPreflightError, match="LIVEKIT_URL"):
        validate_voice_worker_environment(data)


def test_worker_never_boots_in_unreviewed_development_mode():
    data = valid_env()
    data["APP_ENV"] = "development"
    with pytest.raises(VoiceWorkerPreflightError, match="APP_ENV"):
        validate_voice_worker_environment(data)


def test_weak_secret_blocks_worker():
    data = valid_env()
    data["SECRET_KEY"] = "weak"
    with pytest.raises(VoiceWorkerPreflightError, match="SECRET_KEY"):
        validate_voice_worker_environment(data)


@pytest.mark.parametrize("key,value", [
    ("DATABASE_URL", "sqlite:///voice.db"),
    ("REDIS_URL", "http://localhost"),
    ("VOICE_AGENT_NAME", "../wrong-room"),
])
def test_incompatible_backend_or_agent_settings_block_worker(key, value):
    data = valid_env()
    data[key] = value
    with pytest.raises(VoiceWorkerPreflightError):
        validate_voice_worker_environment(data)


@pytest.mark.parametrize("name,value", [
    ("AQLYRA_PROCESS_ROLE", "api"),
    ("RATE_LIMIT_ENABLED", "false"),
    ("RAG_GROUNDING_VERIFIER_ENABLED", "false"),
    ("LLM_PROVIDER", "deterministic"),
    ("EMBEDDING_PROVIDER", "deterministic"),
    ("HF_TOKEN", ""),
])
def test_worker_cannot_bypass_production_role_and_provider_guards(name, value):
    data = valid_env()
    data[name] = value
    with pytest.raises(VoiceWorkerPreflightError):
        validate_voice_worker_environment(data)

def test_openai_embeddings_need_own_provider_key():
    data = valid_env()
    data["EMBEDDING_PROVIDER"] = "openai"
    with pytest.raises(VoiceWorkerPreflightError, match="OPENAI_API_KEY"):
        validate_voice_worker_environment(data)


def remote_onnx_voice_env():
    data = valid_env()
    data.update({
        "EMBEDDING_PROVIDER": "remote_onnx",
        "EMBEDDING_MODEL": "bekko-static-multilingual-int8-mrl384-v1",
        "EMBEDDING_DIMENSION": "384",
        "REMOTE_SEMANTIC_URL": "https://aqlyra-semantic-worker.onrender.com",
        "REMOTE_SEMANTIC_TOKEN": "synthetic-nonproduction-token-for-tests-12345",
    })
    data.pop("HF_TOKEN", None)
    return data


def test_voice_remote_semantic_production_compatible():
    validate_voice_worker_environment(remote_onnx_voice_env())


@pytest.mark.parametrize("key", [
    "REMOTE_SEMANTIC_URL", "REMOTE_SEMANTIC_TOKEN",
    "EMBEDDING_MODEL", "EMBEDDING_DIMENSION",
])
def test_remote_semantic_missing_keys_fail_closed(key):
    data = remote_onnx_voice_env()
    data[key] = ""
    with pytest.raises(VoiceWorkerPreflightError, match=key):
        validate_voice_worker_environment(data)


@pytest.mark.parametrize("key,value", [
    ("EMBEDDING_MODEL", "deterministic-sha256-v1"),
    ("EMBEDDING_DIMENSION", "768"),
    ("REMOTE_SEMANTIC_URL", "http://aqlyra-semantic-worker.onrender.com"),
    ("REMOTE_SEMANTIC_URL", "https://wrong-worker.onrender.com"),
    ("REMOTE_SEMANTIC_URL", "https://aqlyra-semantic-worker.onrender.com@evil.com"),
    ("REMOTE_SEMANTIC_TOKEN", "short"),
])
def test_remote_semantic_voice_rejects_untrusted_runtime(key, value):
    data = remote_onnx_voice_env()
    data[key] = value
    with pytest.raises(VoiceWorkerPreflightError):
        validate_voice_worker_environment(data)
