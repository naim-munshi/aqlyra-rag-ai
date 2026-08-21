from contextvars import ContextVar, Token
from datetime import timezone
import json
import logging
import re
import sys
import traceback
from typing import Any

from loguru import logger

from app.config.settings import settings


_REQUEST_ID: ContextVar[str] = ContextVar(
    "aqlyra_request_id",
    default="-",
)

_CONFIGURED = False


_SECRET_PATTERNS = (
    (
        re.compile(
            r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"
        ),
        "Bearer [REDACTED]",
    ),
    (
        re.compile(
            r"\bgsk_[A-Za-z0-9_-]{8,}\b"
        ),
        "[REDACTED_API_KEY]",
    ),
    (
        re.compile(
            r"\bhf_[A-Za-z0-9_-]{8,}\b"
        ),
        "[REDACTED_TOKEN]",
    ),
    (
        re.compile(
            r"\bsk-[A-Za-z0-9_-]{8,}\b"
        ),
        "[REDACTED_API_KEY]",
    ),
    (
        re.compile(
            r"(?i)\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"
        ),
        "[REDACTED_EMAIL]",
    ),
)


_SENSITIVE_KEY = re.compile(
    r"(?i)(password|passwd|pwd|secret|"
    r"authorization|access[_-]?token|"
    r"api[_-]?key|livekit[_-]?api[_-]?secret)"
)


def get_request_id() -> str:
    return _REQUEST_ID.get()


def set_request_id(
    request_id: str,
) -> Token[str]:
    return _REQUEST_ID.set(
        request_id
    )


def reset_request_id(
    token: Token[str],
) -> None:
    _REQUEST_ID.reset(
        token
    )


_URL_QUERY_PATTERN = re.compile(
    r"""(?i)(https?://[^\s"'?]+)\?[^\s"']*"""
)


def _sanitize_text(
    value: str,
    *,
    max_length: int = 12_000,
) -> str:
    cleaned = _URL_QUERY_PATTERN.sub(
        lambda match: (
            match.group(1)
            + "?[REDACTED_QUERY]"
        ),
        value,
    )

    for pattern, replacement in (
        _SECRET_PATTERNS
    ):
        cleaned = pattern.sub(
            replacement,
            cleaned,
        )

    if len(cleaned) > max_length:
        cleaned = (
            cleaned[:max_length]
            + "...[TRUNCATED]"
        )

    return cleaned

def _safe_value(
    key: str,
    value: Any,
) -> Any:
    if _SENSITIVE_KEY.search(
        key
    ):
        return "[REDACTED]"

    if value is None or isinstance(
        value,
        (
            bool,
            int,
            float,
        ),
    ):
        return value

    if isinstance(
        value,
        str,
    ):
        return _sanitize_text(
            value,
            max_length=2_048,
        )

    if isinstance(
        value,
        dict,
    ):
        return {
            str(child_key): _safe_value(
                str(child_key),
                child_value,
            )
            for (
                child_key,
                child_value,
            ) in list(
                value.items()
            )[:50]
        }

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):
        return [
            _safe_value(
                key,
                item,
            )
            for item in list(
                value
            )[:50]
        ]

    return _sanitize_text(
        str(value),
        max_length=2_048,
    )


def _inject_context(
    record: dict,
) -> None:
    record["message"] = _sanitize_text(
        str(
            record["message"]
        ),
        max_length=4_096,
    )

    record["extra"].setdefault(
        "request_id",
        get_request_id(),
    )

def _json_sink(
    message,
) -> None:
    record = message.record

    extra = dict(
        record["extra"]
    )

    request_id = str(
        extra.pop(
            "request_id",
            get_request_id(),
        )
    )

    source_logger = str(
        extra.pop(
            "source_logger",
            record["name"],
        )
    )

    payload: dict[str, Any] = {
        "timestamp": (
            record["time"]
            .astimezone(
                timezone.utc
            )
            .isoformat()
            .replace(
                "+00:00",
                "Z",
            )
        ),
        "level": (
            record["level"].name
        ),
        "event": _sanitize_text(
            str(
                record["message"]
            ),
            max_length=4_096,
        ),
        "logger": source_logger,
        "request_id": request_id,
        "environment": (
            settings.APP_ENV
        ),
        "service": (
            settings.PROJECT_NAME
        ),
    }

    for key, value in (
        extra.items()
    ):
        payload[str(key)] = (
            _safe_value(
                str(key),
                value,
            )
        )

    exception = (
        record["exception"]
    )

    if exception is not None:
        payload["exception_type"] = (
            exception.type.__name__
        )

        payload["exception"] = (
            _sanitize_text(
                str(
                    exception.value
                ),
                max_length=4_096,
            )
        )

        payload["traceback"] = (
            _sanitize_text(
                "".join(
                    traceback.format_exception(
                        exception.type,
                        exception.value,
                        exception.traceback,
                    )
                ),
                max_length=12_000,
            )
        )

    sys.stdout.write(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(
                ",",
                ":",
            ),
            default=str,
        )
        + "\n"
    )

    sys.stdout.flush()


class _InterceptHandler(
    logging.Handler
):
    def emit(
        self,
        record: logging.LogRecord,
    ) -> None:
        try:
            level: str | int = (
                logger.level(
                    record.levelname
                ).name
            )
        except ValueError:
            level = (
                record.levelno
            )

        logger.bind(
            source_logger=record.name
        ).opt(
            exception=record.exc_info
        ).log(
            level,
            _sanitize_text(
                record.getMessage(),
                max_length=4_096,
            ),
        )


def configure_logging() -> None:
    global _CONFIGURED

    if _CONFIGURED:
        return

    _CONFIGURED = True

    level = str(
        getattr(
            settings,
            "LOG_LEVEL",
            "INFO",
        )
    ).upper()

    logger.remove()

    logger.configure(
        patcher=_inject_context
    )

    if settings.is_production:
        logger.add(
            _json_sink,
            level=level,
            backtrace=False,
            diagnose=False,
            enqueue=False,
            catch=True,
        )
    else:
        logger.add(
            sys.stdout,
            level=level,
            format=(
                "{time:YYYY-MM-DD HH:mm:ss.SSS}"
                " | {level}"
                " | request_id={extra[request_id]}"
                " | {message}"
            ),
            backtrace=False,
            diagnose=False,
            enqueue=False,
        )

    intercept = (
        _InterceptHandler()
    )

    root_logger = (
        logging.getLogger()
    )

    root_logger.handlers = [
        intercept
    ]

    root_logger.setLevel(
        level
    )

    for logger_name in (
        "uvicorn",
        "uvicorn.error",
    ):
        std_logger = (
            logging.getLogger(
                logger_name
            )
        )

        std_logger.handlers = [
            intercept
        ]

        std_logger.propagate = False
        std_logger.setLevel(
            level
        )

    access_logger = (
        logging.getLogger(
            "uvicorn.access"
        )
    )

    access_logger.handlers = []
    access_logger.propagate = False
    access_logger.disabled = True


configure_logging()

app_logger = logger
