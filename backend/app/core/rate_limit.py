from functools import lru_cache
import hashlib
import ipaddress
import math

from fastapi import (
    HTTPException,
    Request,
    status,
)
from redis import Redis
from redis.exceptions import RedisError

from app.auth.security import (
    InvalidTokenError,
    decode_access_token,
)
from app.config.settings import settings
from app.core.logging import app_logger
from app.core.monitoring import (
    record_rate_limit_backend_unavailable,
    record_rate_limit_exceeded,
)


_RATE_LIMIT_SCRIPT = """
local current = redis.call("INCR", KEYS[1])

if current == 1 then
    redis.call(
        "EXPIRE",
        KEYS[1],
        ARGV[1]
    )
end

local ttl = redis.call(
    "TTL",
    KEYS[1]
)

return {
    current,
    ttl
}
""".strip()


@lru_cache(maxsize=1)
def get_rate_limit_redis() -> Redis:
    return Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=(
            settings
            .RATE_LIMIT_REDIS_TIMEOUT_SECONDS
        ),
        socket_timeout=(
            settings
            .RATE_LIMIT_REDIS_TIMEOUT_SECONDS
        ),
    )


def _hashed_identity(
    value: str,
) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def _rate_limit_key(
    *,
    bucket: str,
    identity: str,
) -> str:
    return (
        "aqlyra:rate-limit:"
        f"{bucket}:"
        f"{_hashed_identity(identity)}"
    )


def _resolve_client_ip(
    request: Request,
) -> str:
    configured_header = (
        settings
        .RATE_LIMIT_CLIENT_IP_HEADER
        .strip()
    )

    if configured_header:
        forwarded_value = (
            request.headers.get(
                configured_header
            )
        )

        if forwarded_value:
            candidate = (
                forwarded_value.strip()
            )

            try:
                return str(
                    ipaddress.ip_address(
                        candidate
                    )
                )
            except ValueError:
                pass

    if (
        request.client is not None
        and request.client.host
    ):
        return request.client.host.strip()

    return "unknown-client"


def _authenticated_subject(
    request: Request,
) -> str | None:
    authorization = (
        request.headers.get(
            "Authorization",
            "",
        )
    )

    scheme, _, token = (
        authorization.partition(" ")
    )

    if (
        scheme.casefold() != "bearer"
        or not token.strip()
    ):
        return None

    try:
        return decode_access_token(
            token.strip()
        )

    except InvalidTokenError:
        return None


def _raise_unavailable(
    *,
    bucket: str,
) -> None:
    record_rate_limit_backend_unavailable(
        bucket
    )

    app_logger.error(
        "rate_limit_backend_unavailable",
        bucket=bucket,
    )

    raise HTTPException(
        status_code=(
            status.HTTP_503_SERVICE_UNAVAILABLE
        ),
        detail=(
            "Rate limiting service "
            "is unavailable"
        ),
    )


def enforce_rate_limit(
    *,
    bucket: str,
    identity: str,
    limit: int,
    window_seconds: int,
) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return

    if (
        limit < 1
        or window_seconds < 1
    ):
        app_logger.error(
            "rate_limit_configuration_invalid "
            f"bucket={bucket}"
        )

        raise HTTPException(
            status_code=(
                status
                .HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Rate limiting configuration "
                "is invalid"
            ),
        )

    redis_key = _rate_limit_key(
        bucket=bucket,
        identity=identity,
    )

    try:
        result = (
            get_rate_limit_redis()
            .eval(
                _RATE_LIMIT_SCRIPT,
                1,
                redis_key,
                window_seconds,
            )
        )

    except RedisError:
        _raise_unavailable(
            bucket=bucket
        )

    if (
        not isinstance(
            result,
            (list, tuple),
        )
        or len(result) != 2
    ):
        _raise_unavailable(
            bucket=bucket
        )

    try:
        current = int(result[0])
        ttl = int(result[1])

    except (
        TypeError,
        ValueError,
    ):
        _raise_unavailable(
            bucket=bucket
        )

    if current <= limit:
        return

    retry_after = (
        ttl
        if ttl > 0
        else window_seconds
    )

    retry_after = max(
        1,
        math.ceil(
            retry_after
        ),
    )

    record_rate_limit_exceeded(
        bucket
    )

    app_logger.warning(
        "rate_limit_exceeded",
        bucket=bucket,
        limit=limit,
        window_seconds=(
            window_seconds
        ),
        retry_after=(
            retry_after
        ),
    )

    raise HTTPException(
        status_code=(
            status.HTTP_429_TOO_MANY_REQUESTS
        ),
        detail="Too many requests",
        headers={
            "Retry-After": str(
                retry_after
            ),
        },
    )


def _enforce_ip_limit(
    *,
    request: Request,
    bucket: str,
    limit: int,
    window_seconds: int,
) -> None:
    enforce_rate_limit(
        bucket=bucket,
        identity=(
            "ip:"
            + _resolve_client_ip(
                request
            )
        ),
        limit=limit,
        window_seconds=(
            window_seconds
        ),
    )


def _enforce_user_limit(
    *,
    request: Request,
    bucket: str,
    limit: int,
    window_seconds: int,
) -> None:
    subject = (
        _authenticated_subject(
            request
        )
    )

    if subject is None:
        return

    enforce_rate_limit(
        bucket=bucket,
        identity=(
            f"user:{subject}"
        ),
        limit=limit,
        window_seconds=(
            window_seconds
        ),
    )


def limit_register_request(
    request: Request,
) -> None:
    _enforce_ip_limit(
        request=request,
        bucket="register-ip",
        limit=(
            settings
            .RATE_LIMIT_REGISTER_IP_LIMIT
        ),
        window_seconds=(
            settings
            .RATE_LIMIT_REGISTER_IP_WINDOW_SECONDS
        ),
    )


def limit_login_request(
    request: Request,
) -> None:
    _enforce_ip_limit(
        request=request,
        bucket="login-ip",
        limit=(
            settings
            .RATE_LIMIT_LOGIN_IP_LIMIT
        ),
        window_seconds=(
            settings
            .RATE_LIMIT_LOGIN_IP_WINDOW_SECONDS
        ),
    )


def limit_login_identity(
    email: str,
) -> None:
    enforce_rate_limit(
        bucket="login-identity",
        identity=(
            "email:"
            + email.strip().casefold()
        ),
        limit=(
            settings
            .RATE_LIMIT_LOGIN_IDENTITY_LIMIT
        ),
        window_seconds=(
            settings
            .RATE_LIMIT_LOGIN_IDENTITY_WINDOW_SECONDS
        ),
    )


def limit_upload_request(
    request: Request,
) -> None:
    _enforce_user_limit(
        request=request,
        bucket="upload-user",
        limit=(
            settings
            .RATE_LIMIT_UPLOAD_USER_LIMIT
        ),
        window_seconds=(
            settings
            .RATE_LIMIT_UPLOAD_USER_WINDOW_SECONDS
        ),
    )


def limit_process_request(
    request: Request,
) -> None:
    _enforce_user_limit(
        request=request,
        bucket="process-user",
        limit=(
            settings
            .RATE_LIMIT_PROCESS_USER_LIMIT
        ),
        window_seconds=(
            settings
            .RATE_LIMIT_PROCESS_USER_WINDOW_SECONDS
        ),
    )


def limit_rag_request(
    request: Request,
) -> None:
    _enforce_user_limit(
        request=request,
        bucket="rag-user",
        limit=(
            settings
            .RATE_LIMIT_RAG_USER_LIMIT
        ),
        window_seconds=(
            settings
            .RATE_LIMIT_RAG_USER_WINDOW_SECONDS
        ),
    )


def limit_chat_request(
    request: Request,
) -> None:
    _enforce_user_limit(
        request=request,
        bucket="chat-user",
        limit=(
            settings
            .RATE_LIMIT_CHAT_USER_LIMIT
        ),
        window_seconds=(
            settings
            .RATE_LIMIT_CHAT_USER_WINDOW_SECONDS
        ),
    )


def limit_voice_request(
    request: Request,
) -> None:
    _enforce_user_limit(
        request=request,
        bucket="voice-user",
        limit=(
            settings
            .RATE_LIMIT_VOICE_USER_LIMIT
        ),
        window_seconds=(
            settings
            .RATE_LIMIT_VOICE_USER_WINDOW_SECONDS
        ),
    )
