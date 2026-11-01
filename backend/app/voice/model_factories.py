"""LiveKit Inference speech by default; direct Groq is explicit opt-in.

AqlyraVoiceAgent.llm_node generates answers via execute_chat_turn.
Importing this module does not create provider clients or contact networks.
"""
from __future__ import annotations
from app.config.settings import settings

def build_voice_stt(*, prompt: str, cfg=settings, inference_factory=None, groq_factory=None):
    if cfg.VOICE_STT_PROVIDER == "livekit":
        if inference_factory is None:
            from livekit.agents import inference
            inference_factory = inference.STT
        return inference_factory(model=cfg.VOICE_STT_MODEL, language=cfg.VOICE_STT_LANGUAGE)
    if cfg.VOICE_STT_PROVIDER == "groq":
        if not cfg.GROQ_API_KEY.strip():
            raise RuntimeError("Direct Groq speech provider not configured")
        if groq_factory is None:
            from livekit.plugins import groq
            groq_factory = groq.STT
        return groq_factory(
            model=cfg.VOICE_STT_MODEL, api_key=cfg.GROQ_API_KEY,
            detect_language=True, prompt=prompt,
        )
    raise ValueError("Unsupported voice STT provider")

def build_session_llm(*, cfg=settings, inference_factory=None, groq_factory=None):
    if cfg.VOICE_SESSION_LLM_PROVIDER == "livekit":
        if inference_factory is None:
            from livekit.agents import inference
            inference_factory = inference.LLM
        return inference_factory(model=cfg.VOICE_SESSION_LLM_MODEL)
    if cfg.VOICE_SESSION_LLM_PROVIDER == "groq":
        if not cfg.GROQ_API_KEY.strip():
            raise RuntimeError("Direct Groq session model not configured")
        if groq_factory is None:
            from livekit.plugins import groq
            groq_factory = groq.LLM
        return groq_factory(
            model=cfg.VOICE_SESSION_LLM_MODEL, api_key=cfg.GROQ_API_KEY,
        )
    raise ValueError("Unsupported voice session LLM provider")
