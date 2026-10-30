"""Offline regression for owner-only LiveKit deploy secrets; no real secrets."""
import importlib.util
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest

FILE = Path(__file__).with_name("livekit_voice_secrets_preflight.py")
spec = importlib.util.spec_from_file_location("aqlyra_voice_preflight", FILE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

FAKE = {
    "SECRET_KEY": "offline-only-not-real-secret-2026-mock-key-0123456789",
    "DATABASE_URL": (
        "postgresql+psycopg://neondb_owner:fake%40secret@"
        "ep-test.ap-southeast-1.aws.neon.tech/neondb?"
        "sslmode=require&channel_binding=require"
    ),
    "REDIS_URL": "rediss://default:fake%40secret@mock.upstash.io:6379",
    "GROQ_API_KEY": "offline-groq-test",
    "HF_TOKEN": "offline-hf-test",
    "GOOGLE_CLIENT_ID": "offline-google-test",
    "RESEND_API_KEY": "offline-resend-test",
    "SMTP_FROM_EMAIL": "robot@example.invalid",
    "EMAIL_DELIVERY_PROVIDER": "resend",
    "LLM_PROVIDER": "groq",
    "EMBEDDING_PROVIDER": "huggingface",
    "RAG_GROUNDING_VERIFIER_ENABLED": "true",
    "RATE_LIMIT_ENABLED": "true",
    "CORS_ORIGINS": "https://aqlyra-ai.vercel.app",
    "APP_ENV": "production",
    "DEBUG": "false",
    "VOICE_AGENT_NAME": "aqlyra-voice",
}


class VoiceSecretsPreflightTest(unittest.TestCase):
    def test_valid_offline_file_is_read_only_and_opaque(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "voice.env"
            file.write_text(
                "# synthetic test values, not credentials\n"
                + "\n".join(f"{k}={v}" for k, v in FAKE.items())
            )
            file.chmod(0o600)
            before = file.read_bytes()
            out, err = StringIO(), StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = module.main(["--secrets-file", str(file)])
            self.assertEqual(code, 0)
            self.assertEqual(file.read_bytes(), before)
            self.assertEqual(
                out.getvalue(),
                "LIVEKIT_SECRETS_PREFLIGHT=PASS\nLIVEKIT_DEPLOYMENT=NOT_RUN\n",
            )
            self.assertNotIn("fake%40secret", out.getvalue() + err.getvalue())

    def test_rejects_every_unsafe_provider_or_runtime_setting(self):
        cases = [
            ("DATABASE_URL", "postgresql://postgres:fake@localhost/db"),
            ("DATABASE_URL", FAKE["DATABASE_URL"].replace(
                "sslmode=require", "sslmode=disable"
            )),
            ("REDIS_URL", "redis://default:fake@cache.upstash.io"),
            ("REDIS_URL", "rediss://default:fake@localhost:6379"),
            ("CORS_ORIGINS", "*"),
            ("DEBUG", "true"),
            ("LLM_PROVIDER", "deterministic"),
            ("EMBEDDING_PROVIDER", "deterministic"),
            ("RATE_LIMIT_ENABLED", "false"),
            ("RAG_GROUNDING_VERIFIER_ENABLED", "false"),
            ("VOICE_AGENT_NAME", "other-voice"),
            ("APP_ENV", "development"),
            ("SECRET_KEY", "short"),
        ]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                entries = {**FAKE, key: value}
                with self.assertRaises(module.VoicePreflightBlocked):
                    module.validate(entries)

        with self.assertRaises(module.VoicePreflightBlocked):
            module.validate({k: v for k, v in FAKE.items() if k != "HF_TOKEN"})
        with self.assertRaises(module.VoicePreflightBlocked):
            module.validate({**FAKE, "LIVEKIT_API_KEY": "test-only-dont-upload"})

    def test_gmail_api_sender_configuration_uses_owner_secrets(self):
        gmail = {
            **{k: v for k, v in FAKE.items() if k != "RESEND_API_KEY"},
            "EMAIL_DELIVERY_PROVIDER": "gmail_api",
            "GMAIL_OAUTH_CLIENT_ID": "offline-client.apps.googleusercontent.com",
            "GMAIL_OAUTH_CLIENT_SECRET": "offline-synthetic-secret",
            "GMAIL_OAUTH_REFRESH_TOKEN": "offline-synthetic-refresh",
        }
        module.validate(gmail)
        for key in (
            "GMAIL_OAUTH_CLIENT_ID",
            "GMAIL_OAUTH_CLIENT_SECRET",
            "GMAIL_OAUTH_REFRESH_TOKEN",
        ):
            with self.subTest(missing=key):
                incomplete = {k: v for k, v in gmail.items() if k != key}
                with self.assertRaises(module.VoicePreflightBlocked):
                    module.validate(incomplete)

    def test_provider_switch_without_valid_credentials_is_blocked(self):
        with self.assertRaises(module.VoicePreflightBlocked):
            module.validate({**FAKE, "EMAIL_DELIVERY_PROVIDER": "gmail_api"})
        with self.assertRaises(module.VoicePreflightBlocked):
            module.validate({**FAKE, "EMAIL_DELIVERY_PROVIDER": "disabled"})
        with self.assertRaises(module.VoicePreflightBlocked):
            module.validate({k: v for k, v in FAKE.items() if k != "RESEND_API_KEY"})

    def test_url_never_accepts_connection_redirection(self):
        for bad in (
            FAKE["DATABASE_URL"] + "&host=attacker.invalid",
            FAKE["DATABASE_URL"] + "&hostaddr=127.0.0.1",
            FAKE["DATABASE_URL"] + "#fragment",
            FAKE["DATABASE_URL"] + "&sslmode=disable",
        ):
            with self.subTest(variant=bad[-32:]):
                self.assertFalse(module.approved_url(bad, redis=False))

    def test_private_file_mode_symlink_duplicate_and_shell_expansion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / "voice.env"
            file.write_text("SECRET_KEY=not-a-real-test\n")
            file.chmod(0o644)
            with self.assertRaises(module.VoicePreflightBlocked):
                module.load_secrets(file)
            file.chmod(0o600)
            file.write_text("SECRET_KEY=a\nSECRET_KEY=b\n")
            with self.assertRaises(module.VoicePreflightBlocked):
                module.load_secrets(file)
            file.write_text("SECRET_KEY=$" + "{EXTERNAL}\n")
            with self.assertRaises(module.VoicePreflightBlocked):
                module.load_secrets(file)
            file.write_text("SECRET_KEY=<placeholder>\n")
            with self.assertRaises(module.VoicePreflightBlocked):
                module.load_secrets(file)
            link = root / "link.env"
            link.symlink_to(file)
            with self.assertRaises(module.VoicePreflightBlocked):
                module.load_secrets(link)

    def test_blocked_cli_never_echoes_private_data(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "voice.env"
            file.write_text("DATABASE_URL=" + FAKE["DATABASE_URL"] + "\n")
            file.chmod(0o600)
            out, err = StringIO(), StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                result = module.main(["--secrets-file", str(file)])
            self.assertEqual(result, 2)
            self.assertEqual(out.getvalue(), "")
            self.assertEqual(err.getvalue(), "LIVEKIT_SECRETS_PREFLIGHT=BLOCKED\n")
            self.assertNotIn("fake%40secret", err.getvalue())


if __name__ == "__main__":
    unittest.main()
