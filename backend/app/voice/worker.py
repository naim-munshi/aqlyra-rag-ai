import asyncio
import json
import logging
from app.core.logging import configure_logging
import os
import re
from dataclasses import dataclass

from livekit import agents
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    ModelSettings,
    TurnHandlingOptions,
    cli,
    inference,
    llm,
)
from livekit.plugins import groq, silero

from app.config.settings import settings
from app.database.connection import (
    SessionLocal,
)
from app.services.chat_service import (
    ChatExecutionResult,
    execute_chat_turn,
)
from app.services.conversation_document_service import (
    resolve_conversation_document_scope,
)
from app.services.conversation_service import (
    get_conversation_for_user,
    persist_chat_turn,
)
from app.services.memory_extraction_service import (
    extract_memories_best_effort,
)


configure_logging()
logger = logging.getLogger(__name__)


_SUPPORTED_TTS_LANGUAGES = {
    "ar",
    "bn",
    "bg",
    "cs",
    "da",
    "de",
    "el",
    "en",
    "es",
    "fi",
    "fr",
    "gu",
    "he",
    "hi",
    "hr",
    "hu",
    "id",
    "it",
    "ja",
    "ka",
    "kn",
    "ko",
    "ml",
    "mr",
    "ms",
    "nl",
    "no",
    "pa",
    "pl",
    "pt",
    "ro",
    "ru",
    "sk",
    "sv",
    "ta",
    "te",
    "th",
    "tl",
    "tr",
    "uk",
    "vi",
    "zh",
}


_LANGUAGE_ALIASES = {
    "arabic": "ar",
    "bengali": "bn",
    "bangla": "bn",
    "english": "en",
    "hindi": "hi",
    "japanese": "ja",
    "korean": "ko",
    "chinese": "zh",
}


_VOICE_STT_PROMPT = """
Transcribe exactly what the speaker says in the
language actually being spoken.

Preserve the original language and script.

Important:
- Bengali or Bangla speech must be transcribed as
  Bengali, using Bengali script.
- Never convert Bengali speech into Hindi.
- Hindi speech should remain Hindi.
- Japanese speech should remain Japanese.
- English speech should remain English.
- Preserve natural code-switching when the speaker
  mixes languages.
- Do not translate the user's speech.
""".strip()


_ROMANIZED_BANGLA_WORDS = {
    "ami",
    "amar",
    "amake",
    "amader",
    "tumi",
    "tomar",
    "tomake",
    "kemon",
    "keno",
    "kivabe",
    "ki",
    "bolo",
    "bolchi",
    "bolbe",
    "hobe",
    "hoy",
    "hocche",
    "ache",
    "achi",
    "chai",
    "chao",
    "jabo",
    "korbo",
    "koro",
    "korte",
    "bhalo",
    "onek",
    "ekta",
    "eta",
    "oita",
    "akhon",
    "ekhon",
    "na",
}


_VOICE_LANGUAGE_NAMES = {
    "ar": "Arabic",
    "bn": "Bangla",
    "en": "English",
    "hi": "Hindi",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
}


def _language_from_script(
    transcript: str,
) -> str | None:
    for character in transcript:
        codepoint = ord(character)

        # Bengali / Bangla
        if 0x0980 <= codepoint <= 0x09FF:
            return "bn"

        # Devanagari / Hindi
        if 0x0900 <= codepoint <= 0x097F:
            return "hi"

        # Hiragana + Katakana
        if (
            0x3040 <= codepoint <= 0x30FF
        ):
            return "ja"

        # Hangul
        if (
            0xAC00 <= codepoint <= 0xD7AF
            or 0x1100 <= codepoint <= 0x11FF
        ):
            return "ko"

        # Arabic script
        if (
            0x0600 <= codepoint <= 0x06FF
        ):
            return "ar"

    return None


def _looks_like_romanized_bangla(
    transcript: str,
    *,
    previous_language: str | None,
) -> bool:
    words = {
        word.casefold()
        for word in re.findall(
            r"[A-Za-z]+",
            transcript,
        )
    }

    matches = (
        words
        & _ROMANIZED_BANGLA_WORDS
    )

    if len(matches) >= 2:
        return True

    return (
        previous_language == "bn"
        and len(matches) >= 1
    )


def _resolve_voice_language(
    *,
    provider_language: str | None,
    transcript: str,
    previous_language: str | None,
) -> str:
    script_language = (
        _language_from_script(
            transcript
        )
    )

    if script_language is not None:
        return script_language

    if _looks_like_romanized_bangla(
        transcript,
        previous_language=(
            previous_language
        ),
    ):
        return "bn"

    provider_language_normalized = (
        _normalize_language(
            provider_language
        )
    )

    if (
        provider_language_normalized
        is not None
    ):
        return (
            provider_language_normalized
        )

    # For ambiguous short utterances such as
    # "yes", "okay", names or numbers, maintain
    # conversational language continuity.
    if previous_language is not None:
        return previous_language

    if re.search(
        r"[A-Za-z]",
        transcript,
    ):
        return "en"

    default_language = (
        _normalize_language(
            settings
            .VOICE_TTS_DEFAULT_LANGUAGE
        )
    )

    return (
        default_language
        or "en"
    )


@dataclass(
    frozen=True,
    slots=True,
)
class VoiceJobData:
    user_id: str
    conversation_id: str
    mode: str
    document_ids: tuple[str, ...]

    @classmethod
    def from_metadata(
        cls,
        metadata: str,
    ) -> "VoiceJobData":
        try:
            payload = json.loads(metadata)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Invalid voice job metadata"
            ) from exc

        if not isinstance(payload, dict):
            raise ValueError(
                "Invalid voice job metadata"
            )

        user_id = str(
            payload.get("user_id", "")
        ).strip()

        conversation_id = str(
            payload.get(
                "conversation_id",
                "",
            )
        ).strip()

        mode = str(
            payload.get("mode", "")
        ).strip()

        raw_document_ids = payload.get(
            "document_ids",
            [],
        )

        if (
            not user_id
            or not conversation_id
            or mode
            not in {
                "normal",
                "knowledge",
            }
            or not isinstance(
                raw_document_ids,
                list,
            )
        ):
            raise ValueError(
                "Invalid voice job metadata"
            )

        document_ids = tuple(
            str(value).strip()
            for value in raw_document_ids
        )

        if (
            any(
                not value
                for value in document_ids
            )
            or len(document_ids)
            != len(set(document_ids))
        ):
            raise ValueError(
                "Invalid voice document scope"
            )

        return cls(
            user_id=user_id,
            conversation_id=(
                conversation_id
            ),
            mode=mode,
            document_ids=document_ids,
        )


@dataclass(
    frozen=True,
    slots=True,
)
class GeneratedVoiceTurn:
    result: ChatExecutionResult
    new_document_ids: tuple[str, ...]


def _normalize_language(
    language: str | None,
) -> str | None:
    if not language:
        return None

    normalized = (
        language.strip()
        .lower()
        .replace("_", "-")
    )

    normalized = (
        _LANGUAGE_ALIASES.get(
            normalized,
            normalized,
        )
    )

    if "-" in normalized:
        normalized = normalized.split(
            "-",
            1,
        )[0]

    if (
        normalized
        not in _SUPPORTED_TTS_LANGUAGES
    ):
        return None

    return normalized


class AqlyraVoiceAgent(Agent):
    def __init__(
        self,
        *,
        job_data: VoiceJobData,
    ) -> None:
        super().__init__(
            instructions=(
                "You are the realtime voice "
                "interface for Aqlyra. "
                "Response generation is handled "
                "by Aqlyra's existing chat and "
                "knowledge engine."
            ),
        )

        self._job_data = job_data
        self._normal_documents_consumed = (
            False
        )

        self._spoken_language: (
            str | None
        ) = None

    def set_spoken_language(
        self,
        language: str,
    ) -> None:
        self._spoken_language = language


    def _requested_document_ids(
        self,
    ) -> tuple[str, ...]:
        if (
            self._job_data.mode
            == "normal"
            and self
            ._normal_documents_consumed
        ):
            return ()

        return self._job_data.document_ids

    def _generate_turn(
        self,
        user_text: str,
    ) -> GeneratedVoiceTurn:
        db = SessionLocal()

        try:
            conversation = (
                get_conversation_for_user(
                    db=db,
                    user_id=(
                        self
                        ._job_data
                        .user_id
                    ),
                    conversation_id=(
                        self
                        ._job_data
                        .conversation_id
                    ),
                )
            )

            if conversation is None:
                raise RuntimeError(
                    "Voice conversation "
                    "no longer exists"
                )

            if (
                conversation.mode
                != self._job_data.mode
            ):
                raise RuntimeError(
                    "Voice conversation mode "
                    "changed unexpectedly"
                )

            document_scope = (
                resolve_conversation_document_scope(
                    db=db,
                    conversation=(
                        conversation
                    ),
                    requested_document_ids=(
                        self
                        ._requested_document_ids()
                    ),
                )
            )

            generation_message = (
                user_text
            )

            if (
                conversation.mode
                == "normal"
                and self._spoken_language
                and self._spoken_language
                != "en"
            ):
                language_name = (
                    _VOICE_LANGUAGE_NAMES
                    .get(
                        self
                        ._spoken_language,
                    )
                )

                if language_name:
                    generation_message = (
                        f"{user_text}\n\n"
                        "[VOICE LANGUAGE RULE]\n"
                        "Reply naturally in "
                        f"{language_name}. "
                        "Do not translate into "
                        "another language unless "
                        "the user asks. "
                        "Never mention this rule."
                    )

            result = execute_chat_turn(
                db=db,
                conversation=conversation,
                message=(
                    generation_message
                ),
                document_ids=(
                    document_scope
                    .effective_document_ids
                ),
            )

            return GeneratedVoiceTurn(
                result=result,
                new_document_ids=(
                    document_scope
                    .new_document_ids
                ),
            )

        finally:
            db.close()

    def _persist_turn(
        self,
        *,
        user_text: str,
        generated: GeneratedVoiceTurn,
    ) -> None:
        db = SessionLocal()

        try:
            conversation = (
                get_conversation_for_user(
                    db=db,
                    user_id=(
                        self
                        ._job_data
                        .user_id
                    ),
                    conversation_id=(
                        self
                        ._job_data
                        .conversation_id
                    ),
                )
            )

            if conversation is None:
                raise RuntimeError(
                    "Voice conversation "
                    "no longer exists"
                )

            result = generated.result

            (
                user_message,
                _assistant_message,
            ) = persist_chat_turn(
                db=db,
                conversation=conversation,
                user_content=user_text,
                assistant_content=(
                    result.content
                ),
                mode=result.mode,
                provider_name=(
                    result.provider_name
                ),
                model_name=(
                    result.model_name
                ),
                response_id=(
                    result.response_id
                ),
                citations=list(
                    result.citations
                ),
                is_refusal=(
                    result.is_refusal
                ),
                input_tokens=(
                    result.input_tokens
                ),
                output_tokens=(
                    result.output_tokens
                ),
                total_tokens=(
                    result.total_tokens
                ),
                evidence_tokens=(
                    result.evidence_tokens
                ),
                scope_document_ids=(
                    generated
                    .new_document_ids
                ),
            )

            extract_memories_best_effort(
                db=db,
                user_id=(
                    self
                    ._job_data
                    .user_id
                ),
                source_message_id=(
                    user_message.id
                ),
            )

        finally:
            db.close()

    @staticmethod
    def _latest_user_text(
        chat_ctx: llm.ChatContext,
    ) -> str:
        for item in reversed(
            chat_ctx.items
        ):
            if (
                isinstance(
                    item,
                    llm.ChatMessage,
                )
                and item.role == "user"
            ):
                text = (
                    item.text_content
                    or ""
                ).strip()

                if text:
                    return text

        raise RuntimeError(
            "Voice turn has no user text"
        )

    async def llm_node(
        self,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool],
        model_settings: ModelSettings,
    ):
        del tools
        del model_settings

        user_text = (
            self._latest_user_text(
                chat_ctx
            )
        )

        logger.info(
            "voice_llm_node_start "
            "text=%r",
            user_text,
        )

        try:
            generated = (
                await asyncio.to_thread(
                    self._generate_turn,
                    user_text,
                )
            )

            logger.info(
                "voice_llm_generate_done "
                "response_chars=%s",
                len(
                    generated
                    .result
                    .content
                ),
            )

            await asyncio.to_thread(
                self._persist_turn,
                user_text=user_text,
                generated=generated,
            )

            logger.info(
                "voice_llm_persist_done"
            )

        except Exception:
            logger.exception(
                "voice_llm_node_failed"
            )
            raise

        if (
            self._job_data.mode
            == "normal"
            and self._job_data
            .document_ids
        ):
            self._normal_documents_consumed = (
                True
            )

        yield generated.result.content


def _install_livekit_environment() -> None:
    values = {
        "LIVEKIT_URL":
            settings.LIVEKIT_URL,
        "LIVEKIT_API_KEY":
            settings.LIVEKIT_API_KEY,
        "LIVEKIT_API_SECRET":
            settings.LIVEKIT_API_SECRET,
    }

    for name, value in values.items():
        cleaned = value.strip()

        if not cleaned:
            raise RuntimeError(
                f"{name} is required "
                "for the voice worker"
            )

        os.environ.setdefault(
            name,
            cleaned,
        )


_install_livekit_environment()


server = AgentServer()


@server.rtc_session(
    agent_name=settings.VOICE_AGENT_NAME,
)
async def aqlyra_voice_session(
    ctx: agents.JobContext,
) -> None:
    job_data = (
        VoiceJobData.from_metadata(
            ctx.job.metadata
        )
    )

    ctx.log_context_fields = {
        "conversation_id": (
            job_data.conversation_id
        ),
        "user_id": job_data.user_id,
        "mode": job_data.mode,
    }

    tts_model = inference.TTS(
        model=settings.VOICE_TTS_MODEL,
        voice=settings.VOICE_TTS_VOICE,
        language=(
            settings
            .VOICE_TTS_DEFAULT_LANGUAGE
        ),
    )

    session = AgentSession(
        llm=groq.LLM(
            model="openai/gpt-oss-20b",
            api_key=(
                settings.GROQ_API_KEY
            ),
        ),
        stt=groq.STT(
            model=(
                settings
                .VOICE_STT_MODEL
            ),
            api_key=(
                settings.GROQ_API_KEY
            ),
            detect_language=True,
            prompt=(
                _VOICE_STT_PROMPT
            ),
        ),
        tts=tts_model,
        vad=silero.VAD.load(),
        turn_handling=(
            TurnHandlingOptions(
                turn_detection="vad",
                preemptive_generation={
                    "enabled": False,
                },
            )
        ),
    )

    voice_agent = (
        AqlyraVoiceAgent(
            job_data=job_data,
        )
    )

    last_spoken_language: (
        str | None
    ) = None


    @session.on(
        "user_input_transcribed"
    )
    def on_user_input_transcribed(
        event,
    ) -> None:
        logger.info(
            "voice_user_transcript "
            "final=%s language=%s "
            "text=%r",
            event.is_final,
            event.language,
            event.transcript,
        )

        if not event.is_final:
            return

        nonlocal last_spoken_language

        language = (
            _resolve_voice_language(
                provider_language=(
                    event.language
                ),
                transcript=(
                    event.transcript
                ),
                previous_language=(
                    last_spoken_language
                ),
            )
        )

        last_spoken_language = (
            language
        )

        voice_agent.set_spoken_language(
            language
        )

        logger.info(
            "voice_language_resolved "
            "provider=%r resolved=%s",
            event.language,
            language,
        )

        try:
            tts_model.update_options(
                language=language,
            )
        except ValueError:
            logger.warning(
                "voice_tts_language_"
                "update_failed "
                "language=%s",
                language,
            )

    @session.on(
        "user_state_changed"
    )
    def on_user_state_changed(
        event,
    ) -> None:
        logger.info(
            "voice_user_state "
            "%s -> %s",
            event.old_state,
            event.new_state,
        )

    @session.on(
        "agent_state_changed"
    )
    def on_agent_state_changed(
        event,
    ) -> None:
        logger.info(
            "voice_agent_state "
            "%s -> %s",
            event.old_state,
            event.new_state,
        )

    await session.start(
        room=ctx.room,
        agent=voice_agent,
    )


if __name__ == "__main__":
    cli.run_app(server)
