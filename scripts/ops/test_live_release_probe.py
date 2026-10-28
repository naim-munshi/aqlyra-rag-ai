"""Offline, credential-free phase contract tests for fixed live Render probe."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch
import importlib.util
import unittest

source = Path(__file__).with_name("live_release_probe.py")
spec = importlib.util.spec_from_file_location("aqlyra_live_phase_probe", source)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

HEALTH = (200, {"status": "healthy"})
READY = (200, {
    "status": "ready",
    "checks": {"database": "ready", "storage": "ready", "redis": "ready"},
})
WORKFLOWS = (200, [{"id": "student", "enabled": True}])


class LivePhaseProbeTest(unittest.TestCase):
    def run_case(self, phase, responses):
        results = iter(responses)
        output = StringIO()
        with patch.object(probe, "probe", side_effect=lambda _: next(results)), \
             redirect_stdout(output):
            status = probe.main(["--expected-phase", phase])
        return status, output.getvalue()

    def test_core_phase_passes_only_when_study_routes_not_deployed(self):
        status, output = self.run_case(
            "core", [HEALTH, READY, (404, None), (404, None)]
        )
        self.assertEqual(status, 0)
        self.assertIn("LIVE_CORE_GATE=PASS", output)
        self.assertIn("FULL_RELEASE_PRODUCTION=NOT_DEPLOYED", output)
        self.assertNotIn("LIVE_RELEASE_GATE=PASS", output)

    def test_full_phase_passes_only_with_full_endpoints(self):
        status, output = self.run_case(
            "full", [HEALTH, READY, WORKFLOWS, (401, None)]
        )
        self.assertEqual(status, 0)
        self.assertIn("LIVE_RELEASE_GATE=PASS", output)
        self.assertNotIn("FULL_RELEASE_PRODUCTION=NOT_DEPLOYED", output)

    def test_full_never_passes_when_only_core_is_live(self):
        status, output = self.run_case(
            "full", [HEALTH, READY, (404, None), (404, None)]
        )
        self.assertEqual(status, 1)
        self.assertIn("LIVE_FULL_GATE=BLOCKED", output)
        self.assertNotIn("LIVE_RELEASE_GATE=PASS", output)

    def test_core_fails_if_full_routes_appear_early(self):
        status, output = self.run_case(
            "core", [HEALTH, READY, WORKFLOWS, (401, None)]
        )
        self.assertEqual(status, 1)
        self.assertIn("LIVE_CORE_GATE=BLOCKED", output)

    def test_no_phase_passes_if_database_not_ready(self):
        broken = (503, {"detail": "Service is not ready"})
        for phase, study, cases in [
            ("core", (404, None), (404, None)),
            ("full", WORKFLOWS, (401, None)),
        ]:
            with self.subTest(phase=phase):
                status, output = self.run_case(
                    phase, [HEALTH, broken, study, cases]
                )
                self.assertEqual(status, 1)
                self.assertIn("BLOCKED database_storage_redis", output)


if __name__ == "__main__":
    unittest.main()
