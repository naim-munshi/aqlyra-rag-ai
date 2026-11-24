"""No credentials or external traffic needed for canary safety unit tests."""
import os
from unittest import TestCase
from unittest.mock import patch

from groq_staging_canary import Sample, check_staging_guards, summarize

SAFE = {
    "AQLYRA_REAL_GROQ_TEST_CONFIRMED": "yes",
    "APP_ENV": "isolated_ci",
    "CI": "true",
    "GITHUB_ACTIONS": "true",
    "AQLYRA_STAGING_GROQ_API_KEY": "synthetic-not-a-real-key",
}

class CanarySafetyTests(TestCase):
    def test_exact_ci_guard(self):
        with patch.dict(os.environ, SAFE, clear=True):
            self.assertEqual(check_staging_guards(), SAFE["AQLYRA_STAGING_GROQ_API_KEY"])

    def test_rejects_production_and_non_dedicated_creds(self):
        for key, wrong in (
            ("APP_ENV", "production"),
            ("CI", "false"),
            ("GITHUB_ACTIONS", "false"),
            ("AQLYRA_REAL_GROQ_TEST_CONFIRMED", "no"),
            ("AQLYRA_TEST_MODEL", "unrestricted-model"),
            ("AQLYRA_STAGING_GROQ_API_KEY", ""),
            ("GROQ_API_KEY", "production-key-must-not-enter-ci"),
        ):
            with self.subTest(key=key), patch.dict(os.environ, SAFE, clear=True):
                os.environ[key] = wrong
                with self.assertRaises(ValueError):
                    check_staging_guards()

    def test_bounded_cost_and_latency_reporting(self):
        one = Sample(True, 321.1, 12, 9, None)
        two = Sample(False, 900.0, None, None, "LLMProviderRateLimitError")
        self.assertEqual(summarize(1, [one])["p95_latency_ms"], 321.1)
        result = summarize(2, [one, two])
        self.assertEqual(result["successes"], 1)
        self.assertEqual(result["p95_latency_ms"], 900.0)
        self.assertEqual(result["input_tokens_reported"], 12)
        self.assertEqual(result["failure_types"], ["LLMProviderRateLimitError"])
        with self.assertRaises(ValueError):
            summarize(3, [one, one, one])
