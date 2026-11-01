"""Pure unit tests: actual live probe is a separate explicit workflow."""
import json
import unittest
from voice_public_security_probe import CHECKS, assess


class VoicePublicSecurityProbeTests(unittest.TestCase):
    def test_pinned_only_aqlyra_hosts(self):
        self.assertEqual(len(CHECKS), 4)
        self.assertTrue(all(item.url.startswith((
            "https://aqlyra-ai.vercel.app/",
            "https://aqlyra-api-free-launch.onrender.com/",
        )) for item in CHECKS))

    def test_authenticated_content_is_not_a_pass(self):
        self.assertEqual(assess(200, "application/json", b'{"participant_token":"token"}', 401), "FAIL")
        self.assertEqual(assess(401, "application/json", b'{"participant_token":"token","detail":"x"}', 401), "FAIL")

    def test_unauthorized_json_response_passes(self):
        self.assertEqual(
            assess(401, "application/json", json.dumps({"detail": "Not authenticated"}).encode(), 401),
            "PASS",
        )
        self.assertEqual(
            assess(403, "application/json", b'{"detail":"Untrusted request origin"}', 403),
            "PASS",
        )

    def test_protected_proxy_or_bad_response_never_passes(self):
        self.assertEqual(assess(401, "text/html", b"<html>login</html>", 401), "BLOCKED")
        self.assertEqual(assess(503, "application/json", b'{"detail":"unavailable"}', 401), "BLOCKED")
        self.assertEqual(assess(302, "text/html", b"", 401), "BLOCKED")
        self.assertEqual(assess(403, "application/json", b'{"detail":"other"}', 403), "BLOCKED")
