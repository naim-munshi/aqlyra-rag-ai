"""Safety regression tests for synthetic, loopback-only E2E helper."""
import unittest

from ephemeral_fullstack_e2e import Client, SmokeFailure, safe_url


class TestEphemeralFullstackE2ESafety(unittest.TestCase):
    def test_loopback_origin_only(self):
        self.assertEqual(safe_url("http://127.0.0.1:8000"), "http://127.0.0.1:8000")
        self.assertEqual(safe_url("http://localhost:8000"), "http://127.0.0.1:8000")

    def test_public_and_private_remote_endpoints_rejected(self):
        unsafe = [
            "https://staging.example.com", "http://192.168.1.2:8000",
            "http://10.0.0.1:8000", "http://[::1]:8001",
            "http://127.0.0.1:5432", "http://127.0.0.1:8000@attacker.invalid",
            "http://127.0.0.1:8000/a", "http://127.0.0.1:8000?x=1",
            "http://127.0.0.1", "http://127.0.0.1:8000#redirect",
        ]
        for url in unsafe:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    safe_url(url)

    def test_only_scoped_v1_paths_allowed(self):
        c = Client("http://127.0.0.1:8000")
        for path in ["https://attacker.invalid", "/api/health", "/api/v1//auth",
                     "/api/v1/../admin"]:
            with self.subTest(path=path):
                with self.assertRaises(SmokeFailure):
                    c.request("GET", path)


if __name__ == "__main__":
    unittest.main()
