"""Safety and reporting contracts for the disposable 10-100 chat benchmark."""
import os
from unittest.mock import patch

import pytest

from ephemeral_chat_load import (
    InFlight, assert_disposable_environment, nearest_rank, valid_chat_reply,
)

GOOD = {
    "AQLYRA_DISPOSABLE_LOAD_CONFIRMED": "yes",
    "APP_ENV": "development",
    "LLM_PROVIDER": "deterministic",
    "EMBEDDING_PROVIDER": "deterministic",
    "EMAIL_VERIFICATION_REQUIRED": "false",
    "RATE_LIMIT_ENABLED": "false",
    "DATABASE_URL": (
        "postgresql+psycopg://postgres:postgres"
        "@localhost:5432/aqlyra_rag_ai"
    ),
}


def test_disposable_loopback_is_required_and_verified():
    with patch.dict(os.environ, GOOD, clear=True):
        assert assert_disposable_environment("http://127.0.0.1:8000") == (
            "http://127.0.0.1:8000"
        )
        for hostile in (
            "https://aqlyra-ai.vercel.app",
            "https://aqlyra-api-free-launch.onrender.com",
            "http://127.0.0.1:5432",
            "http://127.0.0.1:8000/api/v1/health",
            "http://localhost:8000?redirect=example.com",
            "http://127.0.0.1:8000@host.example",
            "http://169.254.169.254:8000",
        ):
            with pytest.raises(ValueError):
                assert_disposable_environment(hostile)


@pytest.mark.parametrize("key,wrong", [
    ("AQLYRA_DISPOSABLE_LOAD_CONFIRMED", "no"),
    ("APP_ENV", "production"),
    ("LLM_PROVIDER", "groq"),
    ("EMBEDDING_PROVIDER", "remote_onnx"),
    ("EMAIL_VERIFICATION_REQUIRED", "true"),
    ("RATE_LIMIT_ENABLED", "true"),
    ("DATABASE_URL", "postgresql+psycopg://postgres:pwd@neon.example.com/app"),
    ("DATABASE_URL", "postgresql+psycopg://postgres:pwd@localhost:5432/aqlyra_production"),
])
def test_no_accidental_live_provider_or_database_workload(key, wrong):
    with patch.dict(os.environ, GOOD, clear=True):
        os.environ[key] = wrong
        with pytest.raises(ValueError):
            assert_disposable_environment("http://127.0.0.1:8000")


def test_latency_nearest_rank_and_authentic_ai_reply_contract():
    assert nearest_rank([], 0.95) is None
    assert nearest_rank([10, 20, 30, 40], 0.5) == 20
    assert nearest_rank([10, 20, 30, 40], 0.95) == 40
    assert nearest_rank([10, 20, 30, 40], 0.99) == 40
    assert not valid_chat_reply(503, None)
    sample = {
        "mode": "normal",
        "user_message": {
            "content": "Briefly greet a synthetic user in one sentence.",
            "role": "user",
        },
        "assistant_message": {
            "content": "Hello!", "role": "assistant",
            "provider_name": "deterministic",
        },
    }
    assert valid_chat_reply(200, sample)
    assert not valid_chat_reply(200, {
        **sample,
        "assistant_message": {
            **sample["assistant_message"],
            "provider_name": "groq",
        },
    })


def test_inflight_counter():
    inflight = InFlight()
    inflight.start()
    inflight.start()
    inflight.done()
    assert inflight.peak == 2
    assert inflight.active == 1
