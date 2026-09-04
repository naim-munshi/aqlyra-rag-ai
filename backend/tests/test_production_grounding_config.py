import os
from pathlib import Path
import subprocess
import sys


ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

BACKEND = ROOT / "backend"

PREFLIGHT = (
    ROOT
    / "scripts"
    / "ops"
    / "production-preflight.sh"
)


def production_values(
) -> dict[str, str]:
    password = (
        "StrongDatabasePassword12345"
    )

    return {
        "PROJECT_NAME": "Aqlyra",
        "VERSION": "1.0.0",
        "API_V1_STR": "/api/v1",
        "APP_ENV": "production",
        "DEBUG": "false",
        "APP_DOMAIN": "app.aqlyra.test",
        "CADDY_EMAIL": "ops@aqlyra.test",
        "CORS_ORIGINS": (
            "https://app.aqlyra.test"
        ),
        "SECRET_KEY": (
            "production-test-secret-key-"
            "with-more-than-32-characters"
        ),
        "ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
        "EMAIL_VERIFICATION_REQUIRED": "true",
        "EMAIL_VERIFICATION_CODE_TTL_MINUTES": "10",
        "EMAIL_VERIFICATION_MAX_ATTEMPTS": "5",
        "EMAIL_VERIFICATION_RESEND_SECONDS": "60",
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "465",
        "SMTP_USERNAME": "sender@gmail.com",
        "SMTP_PASSWORD": "test-google-app-password",
        "SMTP_FROM_EMAIL": "sender@gmail.com",
        "SMTP_FROM_NAME": "Aqlyra",
        "SMTP_USE_SSL": "true",
        "SMTP_TIMEOUT_SECONDS": "10",
        "GOOGLE_CLIENT_ID": "test.apps.googleusercontent.com",
        "POSTGRES_USER": "aqlyra",
        "POSTGRES_PASSWORD": password,
        "POSTGRES_DB": "aqlyra",
        "POSTGRES_PORT": "5432",
        "DATABASE_URL": (
            "postgresql+psycopg://"
            f"aqlyra:{password}"
            "@127.0.0.1:5432/aqlyra"
        ),
        "DATABASE_URL_DOCKER": (
            "postgresql+psycopg://"
            f"aqlyra:{password}"
            "@postgres:5432/aqlyra"
        ),
        "REDIS_URL": (
            "redis://redis:6379/0"
        ),
        "REDIS_URL_DOCKER": (
            "redis://redis:6379/0"
        ),
        "RATE_LIMIT_ENABLED": "true",
        "RATE_LIMIT_CLIENT_IP_HEADER": (
            "X-Aqlyra-Client-IP"
        ),
        "RATE_LIMIT_REDIS_TIMEOUT_SECONDS": "1",
        "RATE_LIMIT_REGISTER_IP_LIMIT": "5",
        "RATE_LIMIT_REGISTER_IP_WINDOW_SECONDS": "3600",
        "RATE_LIMIT_LOGIN_IP_LIMIT": "10",
        "RATE_LIMIT_LOGIN_IP_WINDOW_SECONDS": "60",
        "RATE_LIMIT_LOGIN_IDENTITY_LIMIT": "10",
        "RATE_LIMIT_LOGIN_IDENTITY_WINDOW_SECONDS": "300",
        "RATE_LIMIT_VERIFY_IP_LIMIT": "10",
        "RATE_LIMIT_VERIFY_IP_WINDOW_SECONDS": "300",
        "RATE_LIMIT_RESEND_IP_LIMIT": "5",
        "RATE_LIMIT_RESEND_IP_WINDOW_SECONDS": "3600",
        "RATE_LIMIT_UPLOAD_USER_LIMIT": "20",
        "RATE_LIMIT_UPLOAD_USER_WINDOW_SECONDS": "3600",
        "RATE_LIMIT_PROCESS_USER_LIMIT": "30",
        "RATE_LIMIT_PROCESS_USER_WINDOW_SECONDS": "3600",
        "RATE_LIMIT_RAG_USER_LIMIT": "20",
        "RATE_LIMIT_RAG_USER_WINDOW_SECONDS": "60",
        "RATE_LIMIT_CHAT_USER_LIMIT": "30",
        "RATE_LIMIT_CHAT_USER_WINDOW_SECONDS": "60",
        "RATE_LIMIT_VOICE_USER_LIMIT": "5",
        "RATE_LIMIT_VOICE_USER_WINDOW_SECONDS": "60",
        "LLM_PROVIDER": "groq",
        "LLM_MODEL": (
            "openai/gpt-oss-20b"
        ),
        "LLM_MAX_OUTPUT_TOKENS": "800",
        "LLM_TIMEOUT_SECONDS": "60",
        "LLM_MAX_RETRIES": "2",
        "RAG_GROUNDING_VERIFIER_ENABLED": (
            "true"
        ),
        "RAG_RERANKER_ENABLED": "false",
        "RAG_QUERY_REWRITE_ENABLED": "false",
        "GROQ_API_KEY": "test-groq-key",
        "HF_TOKEN": "test-hf-token",
        "EMBEDDING_PROVIDER": "huggingface",
        "EMBEDDING_MODEL": (
            "ibm-granite/"
            "granite-embedding-97m-"
            "multilingual-r2"
        ),
        "EMBEDDING_DIMENSION": "384",
        "LIVEKIT_URL": (
            "wss://livekit.aqlyra.test"
        ),
        "LIVEKIT_API_KEY": (
            "test-livekit-key"
        ),
        "LIVEKIT_API_SECRET": (
            "test-livekit-secret"
        ),
    }


def write_env(
    path: Path,
    values: dict[str, str],
) -> None:
    path.write_text(
        "".join(
            f"{key}={value}\n"
            for key, value
            in values.items()
        ),
        encoding="utf-8",
    )


def run_preflight(
    env_file: Path,
):
    return subprocess.run(
        [
            "/bin/bash",
            str(PREFLIGHT),
            str(env_file),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={
            **os.environ,
            "AQ_PYTHON_BIN": (
                sys.executable
            ),
        },
    )


def run_settings(
    values: dict[str, str],
):
    clean_env = {
        "PATH": os.environ.get(
            "PATH",
            "",
        ),
        "HOME": os.environ.get(
            "HOME",
            "",
        ),
        "PYTHONPATH": str(BACKEND),
        **values,
    }

    return subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from app.config.settings "
                "import Settings; "
                "Settings(); "
                "print('SETTINGS=PASS')"
            ),
        ],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=False,
        env=clean_env,
    )


def test_production_preflight_accepts_grounded_config(
    tmp_path: Path,
) -> None:
    env_file = (
        tmp_path / "production.env"
    )

    write_env(
        env_file,
        production_values(),
    )

    result = run_preflight(
        env_file
    )

    assert result.returncode == 0, (
        result.stdout,
        result.stderr,
    )

    assert (
        "RAG_GROUNDING_VERIFIER=PASS"
        in result.stdout
    )


def test_production_preflight_rejects_missing_identity_config(
    tmp_path: Path,
) -> None:
    values = production_values()
    values["SMTP_PASSWORD"] = ""
    values["GOOGLE_CLIENT_ID"] = ""
    env_file = tmp_path / "production.env"

    write_env(
        env_file,
        values,
    )
    result = run_preflight(
        env_file
    )

    assert result.returncode != 0
    assert "SMTP_PASSWORD must be configured" in result.stdout
    assert "GOOGLE_CLIENT_ID must be configured" in result.stdout


def test_production_preflight_rejects_disabled_verifier(
    tmp_path: Path,
) -> None:
    values = production_values()

    values[
        "RAG_GROUNDING_VERIFIER_ENABLED"
    ] = "false"

    env_file = (
        tmp_path / "production.env"
    )

    write_env(
        env_file,
        values,
    )

    result = run_preflight(
        env_file
    )

    assert result.returncode != 0

    assert (
        "RAG_GROUNDING_VERIFIER_ENABLED "
        "must be true in production"
        in result.stdout
    )


def test_production_preflight_rejects_deterministic_llm(
    tmp_path: Path,
) -> None:
    values = production_values()

    values["LLM_PROVIDER"] = (
        "deterministic"
    )

    env_file = (
        tmp_path / "production.env"
    )

    write_env(
        env_file,
        values,
    )

    result = run_preflight(
        env_file
    )

    assert result.returncode != 0

    assert (
        "LLM_PROVIDER must be groq or openai"
        in result.stdout
    )


def test_settings_accept_production_grounding(
) -> None:
    result = run_settings(
        production_values()
    )

    assert result.returncode == 0, (
        result.stdout,
        result.stderr,
    )


def test_settings_reject_disabled_production_verifier(
) -> None:
    values = production_values()

    values[
        "RAG_GROUNDING_VERIFIER_ENABLED"
    ] = "false"

    result = run_settings(
        values
    )

    assert result.returncode != 0

    combined = (
        result.stdout
        + result.stderr
    )

    assert (
        "RAG_GROUNDING_VERIFIER_ENABLED"
        in combined
    )


def test_settings_reject_deterministic_production_llm(
) -> None:
    values = production_values()

    values["LLM_PROVIDER"] = (
        "deterministic"
    )

    result = run_settings(
        values
    )

    assert result.returncode != 0

    combined = (
        result.stdout
        + result.stderr
    )

    assert (
        "LLM_PROVIDER"
        in combined
    )


def test_production_preflight_rejects_disabled_rate_limiting(
    tmp_path: Path,
) -> None:
    values = production_values()

    values[
        "RATE_LIMIT_ENABLED"
    ] = "false"

    env_file = (
        tmp_path / "production.env"
    )

    write_env(
        env_file,
        values,
    )

    result = run_preflight(
        env_file
    )

    assert result.returncode != 0

    assert (
        "RATE_LIMIT_ENABLED must be true"
        in result.stdout
    )


def test_settings_reject_disabled_production_rate_limiting(
) -> None:
    values = production_values()

    values[
        "RATE_LIMIT_ENABLED"
    ] = "false"

    result = run_settings(
        values
    )

    assert result.returncode != 0

    combined = (
        result.stdout
        + result.stderr
    )

    assert (
        "RATE_LIMIT_ENABLED"
        in combined
    )
