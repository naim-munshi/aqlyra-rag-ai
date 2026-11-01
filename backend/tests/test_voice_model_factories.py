"""Hybrid LiveKit speech and Groq opt-in; all checks offline."""
from types import SimpleNamespace
import pytest
from app.voice.model_factories import build_session_llm, build_voice_stt
from app.voice.preflight import VoiceWorkerPreflightError, validate_voice_worker_environment
from test_voice_worker_preflight import valid_env

def config(**overrides):
    d = dict(
        VOICE_STT_PROVIDER="livekit", VOICE_STT_MODEL="deepgram/nova-3",
        VOICE_STT_LANGUAGE="multi", VOICE_SESSION_LLM_PROVIDER="livekit",
        VOICE_SESSION_LLM_MODEL="openai/gpt-oss-120b", GROQ_API_KEY="",
    )
    d.update(overrides)
    return SimpleNamespace(**d)

def test_livekit_speech_and_session_run_without_groq_key():
    cfg = config()
    assert build_voice_stt(prompt="Do not translate", cfg=cfg, inference_factory=lambda **x: x) == {
        "model": "deepgram/nova-3", "language": "multi",
    }
    assert build_session_llm(cfg=cfg, inference_factory=lambda **x: x) == {
        "model": "openai/gpt-oss-120b",
    }

def test_preflight_no_groq_required_for_openai_brain():
    d = valid_env()
    d.update(LLM_PROVIDER="openai", OPENAI_API_KEY="synthetic-openai-key", GROQ_API_KEY="")
    validate_voice_worker_environment(d)

@pytest.mark.parametrize("field", ["VOICE_STT_PROVIDER", "VOICE_SESSION_LLM_PROVIDER", "LLM_PROVIDER"])
def test_groq_only_required_when_selected(field):
    d = valid_env()
    d.update(LLM_PROVIDER="openai", OPENAI_API_KEY="synthetic-openai-key", GROQ_API_KEY="")
    d[field] = "groq"
    if field == "VOICE_STT_PROVIDER":
        d["VOICE_STT_MODEL"] = "whisper-large-v3"
    with pytest.raises(VoiceWorkerPreflightError, match="GROQ_API_KEY"):
        validate_voice_worker_environment(d)

def test_explicit_groq_factory_selection():
    cfg = config(
        VOICE_STT_PROVIDER="groq", VOICE_STT_MODEL="whisper-large-v3",
        VOICE_SESSION_LLM_PROVIDER="groq", VOICE_SESSION_LLM_MODEL="openai/gpt-oss-20b",
        GROQ_API_KEY="synthetic-groq-key",
    )
    x = build_voice_stt(prompt="Retain language", cfg=cfg, groq_factory=lambda **kw: kw)
    assert x["model"] == "whisper-large-v3"
    assert x["detect_language"] is True
    assert build_session_llm(cfg=cfg, groq_factory=lambda **kw: kw)["model"] == "openai/gpt-oss-20b"

@pytest.mark.parametrize("field", ["VOICE_STT_PROVIDER", "VOICE_SESSION_LLM_PROVIDER"])
def test_unknown_provider_rejected(field):
    cfg = config(**{field: "unknown"})
    with pytest.raises(ValueError):
        if field == "VOICE_STT_PROVIDER":
            build_voice_stt(prompt="", cfg=cfg)
        else:
            build_session_llm(cfg=cfg)


def test_deepgram_multilingual_hints_bias_bengali_and_japanese_not_lock_language():
    cfg = config(VOICE_STT_LANGUAGE_HINTS="bn,ja,en,hi")
    actual = build_voice_stt(
        prompt="Preserve native script", cfg=cfg, inference_factory=lambda **x: x
    )
    assert actual == {
        "model": "deepgram/nova-3",
        "language": "multi",
        "extra_kwargs": {"language_hint": ["bn", "ja", "en", "hi"]},
    }


@pytest.mark.parametrize("hints", [
    "invalid", "bn,bn", "bn,ja,en,hi,ar,zh,fr", "bn,,ja",
])
def test_deepgram_hints_fail_closed_on_invalid_values(hints):
    cfg = config(VOICE_STT_LANGUAGE_HINTS=hints)
    with pytest.raises(ValueError, match="VOICE_STT_LANGUAGE_HINTS"):
        build_voice_stt(prompt="", cfg=cfg, inference_factory=lambda **x: x)


def test_language_hints_do_not_leak_into_other_stt_models():
    cfg = config(VOICE_STT_MODEL="assemblyai/universal-streaming", VOICE_STT_LANGUAGE_HINTS="bn")
    actual = build_voice_stt(prompt="", cfg=cfg, inference_factory=lambda **x: x)
    assert actual == {
        "model": "assemblyai/universal-streaming", "language": "multi",
    }
