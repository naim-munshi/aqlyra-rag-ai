"""Safety and reporting contracts for disposable 10-100 chat load.

Uses only standard-library unittest: the offline operations merge-gate runs
with the system Python and must not require backend-only pytest packages.
Pytest also discovers these unittest.TestCase methods in backend CI.
"""
import os
import unittest
from unittest.mock import patch

from ephemeral_chat_load import (
    InFlight,
    assert_disposable_environment,
    nearest_rank,
    valid_chat_reply,
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


class DisposableChatLoadSafetyTests(unittest.TestCase):
    def test_disposable_loopback_is_required_and_verified(self):
        with patch.dict(os.environ, GOOD, clear=True):
            self.assertEqual(
                assert_disposable_environment("http://127.0.0.1:8000"),
                "http://127.0.0.1:8000",
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
                with self.subTest(hostile=hostile):
                    with self.assertRaises(ValueError):
                        assert_disposable_environment(hostile)

    def test_no_accidental_live_provider_or_database_workload(self):
        forbidden = (
            ("AQLYRA_DISPOSABLE_LOAD_CONFIRMED", "no"),
            ("APP_ENV", "production"),
            ("LLM_PROVIDER", "groq"),
            ("EMBEDDING_PROVIDER", "remote_onnx"),
            ("EMAIL_VERIFICATION_REQUIRED", "true"),
            ("RATE_LIMIT_ENABLED", "true"),
            ("DATABASE_URL", "postgresql+psycopg://postgres:pwd@neon.example.com/app"),
            ("DATABASE_URL", "postgresql+psycopg://postgres:pwd@localhost:5432/aqlyra_production"),
        )
        for key, wrong in forbidden:
            with self.subTest(key=key, wrong=wrong):
                with patch.dict(os.environ, GOOD, clear=True):
                    os.environ[key] = wrong
                    with self.assertRaises(ValueError):
                        assert_disposable_environment("http://127.0.0.1:8000")

    def test_latency_nearest_rank_and_authentic_ai_reply_contract(self):
        self.assertIsNone(nearest_rank([], 0.95))
        self.assertEqual(nearest_rank([10, 20, 30, 40], 0.5), 20)
        self.assertEqual(nearest_rank([10, 20, 30, 40], 0.95), 40)
        self.assertEqual(nearest_rank([10, 20, 30, 40], 0.99), 40)
        self.assertFalse(valid_chat_reply(503, None))
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
        self.assertTrue(valid_chat_reply(200, sample))
        self.assertFalse(valid_chat_reply(200, {
            **sample,
            "assistant_message": {
                **sample["assistant_message"],
                "provider_name": "groq",
            },
        }))

    def test_inflight_counter(self):
        inflight = InFlight()
        inflight.start()
        inflight.start()
        inflight.done()
        self.assertEqual(inflight.peak, 2)
        self.assertEqual(inflight.active, 1)


if __name__ == "__main__":
    unittest.main()
