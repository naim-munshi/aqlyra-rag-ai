"""Offline unit tests for bounded, credential-free staging probe."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import threading
import unittest

from performance_probe import percentile_nearest_rank


SCRIPT = Path(__file__).with_name("performance_probe.py")


class StubHandler(BaseHTTPRequestHandler):
    healthy = True

    def do_GET(self):
        status = 200 if self.healthy else 503
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b'{"status":"ready"}')

    def log_message(self, fmt, *args):
        pass


class ProbeTests(unittest.TestCase):
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
        StubHandler.healthy = True

    def call_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--base-url", self.url, *args],
            capture_output=True, text=True, check=False, timeout=20,
        )

    def test_percentile_nearest_rank(self):
        self.assertEqual(percentile_nearest_rank([1, 10, 3, 9], 0.5), 3)
        self.assertEqual(percentile_nearest_rank([1, 10, 3, 9], 0.95), 10)
        with self.assertRaises(ValueError):
            percentile_nearest_rank([], 0.95)

    def test_local_bounded_probe_pass(self):
        result = self.call_cli(
            "--allow-http-loopback", "--requests", "8", "--concurrency", "2"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PERFORMANCE_PROBE=PASS", result.stdout)
        self.assertIn("LATENCY_P95_MS=", result.stdout)

    def test_unhealthy_response_fails(self):
        StubHandler.healthy = False
        result = self.call_cli("--allow-http-loopback", "--requests", "4")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ERRORS=4", result.stdout)

    def test_external_http_rejected(self):
        result = self.call_cli("--requests", "1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("HTTPS is required", result.stderr)

    def test_excessive_requests_rejected(self):
        result = self.call_cli("--allow-http-loopback", "--requests", "999")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("between 1 and 100", result.stderr)

    def test_excessive_concurrency_rejected(self):
        result = self.call_cli("--allow-http-loopback", "--concurrency", "99")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("between 1 and 4", result.stderr)


if __name__ == "__main__":
    unittest.main()
