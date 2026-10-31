"""Offline safety/contract tests for disposable two-account artifact API smoke."""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from unittest import TestCase
from unittest.mock import patch
from urllib.error import HTTPError

import artifact_staging_e2e as smoke


class FakeClient:
    def __init__(self, *, fail_download=False):
        self.fail_download = fail_download
        self.records = {}
        self.deleted = []
        self.logins = 0

    def request(self, method, path, *, token="", data=None):
        if path == "/api/v1/auth/login":
            self.logins += 1
            return (200, {}, ('{"access_token":"' + ("A" if self.logins == 1 else "B") * 40 + '"}').encode())
        if path == "/api/v1/artifacts":
            items = [dict(id=key) for key in self.records] if token == "A" * 40 else []
            return (200, {}, ("{\"items\":" + __import__("json").dumps(items) + "}").encode())
        if path == "/api/v1/artifacts/render":
            assert token == "A" * 40
            kind = data["format"]
            artifact_id = f"00000000-0000-4000-8000-{len(self.records) + len(self.deleted) + 1:012d}"
            blob = b"# Staging artifact\nSynthetic staging-only content." if kind == "md" else b"%PDF-1.4\n" if kind == "pdf" else b"PK\x03\x04fixture"
            self.records[artifact_id] = (kind, blob)
            return (201, {}, __import__("json").dumps({"id": artifact_id, "format": kind, "size": len(blob)}).encode())
        artifact_id = path.split("/")[4]
        if token != "A" * 40 or artifact_id not in self.records:
            return (404, {}, b"{}")
        if path.endswith("/download"):
            if self.fail_download:
                return (503, {}, b"{}")
            blob = self.records[artifact_id][1]
            return (200, {
                "Content-Disposition": "attachment; filename=synthetic",
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            }, blob)
        if method == "DELETE":
            self.records.pop(artifact_id)
            self.deleted.append(artifact_id)
            return (204, {}, b"")
        return (200, {}, b"{}")


class ArtifactStagingE2ETests(TestCase):
    def test_known_live_origins_rejected_even_with_acknowledgement(self):
        for host in smoke._PROD_HOSTS:
            with self.subTest(host=host), self.assertRaisesRegex(ValueError, "production"):
                smoke.require_disposable_target("https://" + host, allow_loopback=False)

    def test_arbitrary_or_credentialed_remote_host_rejected(self):
        for url in ("https://example.com", "https://user:pass@staging.example.com",
                    "http://staging.example.com", "https://staging.example.com/path"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                smoke.require_disposable_target(url, allow_loopback=False)

    def test_disposable_staging_and_explicit_local_loopback(self):
        self.assertEqual(
            smoke.require_disposable_target("https://staging.aqlyra.example", allow_loopback=False),
            "https://staging.aqlyra.example",
        )
        self.assertEqual(
            smoke.require_disposable_target("http://127.0.0.1:8000", allow_loopback=True),
            "http://127.0.0.1:8000",
        )
        with self.assertRaises(ValueError):
            smoke.require_disposable_target("http://127.0.0.1:8000", allow_loopback=False)

    def test_full_five_format_sequence_and_owner_isolation(self):
        fake = FakeClient()
        with redirect_stdout(StringIO()) as stream:
            smoke.run(fake, ("owner-a@example.test", "secret-a"),
                       ("owner-b@example.test", "secret-b"))
        self.assertEqual(fake.logins, 2)
        self.assertEqual(len(fake.deleted), 5)
        self.assertEqual(fake.records, {})
        self.assertIn("PASS two-account inventory isolation", stream.getvalue())
        self.assertNotIn("secret-a", stream.getvalue())

    def test_failed_download_still_cleans_exact_created_id(self):
        fake = FakeClient(fail_download=True)
        with redirect_stdout(StringIO()), self.assertRaisesRegex(
            smoke.SmokeFailure, "owner download"
        ):
            smoke.run(fake, ("owner-a@example.test", "a"),
                      ("owner-b@example.test", "b"))
        self.assertEqual(len(fake.deleted), 1)
        self.assertEqual(fake.records, {})

    def test_duplicate_account_is_rejected_before_any_api_call(self):
        fake = FakeClient()
        with self.assertRaisesRegex(smoke.SmokeFailure, "independent"):
            smoke.run(fake, ("USER@example.test", "a"), ("user@example.test", "b"))
        self.assertEqual(fake.logins, 0)

    def test_main_rejects_unconfirmed_staging(self):
        with self.assertRaises(SystemExit) as ctx:
            smoke.main(["--base-url", "https://staging.example.com"])
        self.assertNotEqual(ctx.exception.code, 0)

    def test_file_signature_rejects_wrong_kind(self):
        self.assertTrue(smoke.file_signature_ok("pdf", b"%PDF-1.6"))
        self.assertFalse(smoke.file_signature_ok("pdf", b"PK\x03\x04bad"))
        self.assertFalse(smoke.file_signature_ok("md", b"other"))
