"""Offline contract tests for the deployment smoke checker."""

import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import threading
import unittest


SCRIPT = Path(__file__).with_name("staging_smoke.py")


class StubHandler(BaseHTTPRequestHandler):
    health_ready = True
    unauthorized = True
    secure_headers = True

    def do_GET(self):
        status = {
            "/api/health": 200,
            "/login": 200,
            "/api/auth/me": 401 if self.unauthorized else 200,
            "/api/conversations": 401 if self.unauthorized else 200,
            "/api/v1/metrics": 404,
        }.get(self.path, 404)

        if self.path == "/api/health":
            body = (
                b'{"status":"ready"}'
                if self.health_ready
                else b'{"status":"unavailable"}'
            )
            mime = "application/json"
        else:
            body = b"<html>Login</html>" if self.path == "/login" else b"{}"
            mime = "text/html" if self.path == "/login" else "application/json"

        self.send_response(status)
        self.send_header("Content-Type", mime)
        if self.path == "/api/health":
            self.send_header("Cache-Control", "no-store, max-age=0")
        if self.secure_headers:
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


class StagingSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), StubHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def setUp(self):
        StubHandler.health_ready = True
        StubHandler.unauthorized = True
        StubHandler.secure_headers = True

    def invoke(self, *extra):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--base-url", self.url, *extra],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )

    def test_staging_happy_path(self):
        result = self.invoke("--allow-http-loopback")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("STAGING_SMOKE=PASS", result.stdout)

    def test_plain_http_is_rejected_without_opt_in(self):
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("HTTPS is required", result.stderr)

    def test_readiness_failure_blocks_deployment(self):
        StubHandler.health_ready = False
        result = self.invoke("--allow-http-loopback")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("backend is not ready", result.stderr)

    def test_missing_proxy_security_headers_is_failure(self):
        StubHandler.secure_headers = False
        result = self.invoke("--allow-http-loopback")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("X-Frame-Options", result.stderr)

    def test_unprotected_private_api_is_failure(self):
        StubHandler.unauthorized = False
        result = self.invoke("--allow-http-loopback")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("/api/auth/me: expected HTTP 401", result.stderr)


if __name__ == "__main__":
    unittest.main()
