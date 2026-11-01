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
        options = {"model": cfg.VOICE_STT_MODEL, "language": cfg.VOICE_STT_LANGUAGE}
        # Deepgram Nova-3 in "multi" mode can use language hints as
        # *bias*, not a language lock. Leave other STT providers unchanged.
        raw_hints = getattr(cfg, "VOICE_STT_LANGUAGE_HINTS", "").strip()
        if (
            raw_hints
            and cfg.VOICE_STT_MODEL.startswith("deepgram/nova-3")
            and cfg.VOICE_STT_LANGUAGE == "multi"
        ):
            hints = [hint.strip().lower() for hint in raw_hints.split(",")]
            permitted = {"en", "bn", "ja", "hi", "ar", "zh", "ko", "fr", "de", "es"}
            if (
                len(hints) > 6
                or not hints
                or len(set(hints)) != len(hints)
                or any(hint not in permitted for hint in hints)
            ):
                raise ValueError("VOICE_STT_LANGUAGE_HINTS contains invalid language hints")
            options["extra_kwargs"] = {"language_hint": hints}
        return inference_factory(**options)
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
