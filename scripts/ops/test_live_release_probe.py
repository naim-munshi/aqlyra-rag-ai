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
    def run_case(self, phase, responses, metrics=(401, None)):
        results = iter([*responses, metrics])
        output = StringIO()
        with patch.object(probe, "probe", side_effect=lambda _: next(results)), \
             redirect_stdout(output):
            status = probe.main(["--expected-phase", phase])
        return status, output.getvalue()

    def test_anonymous_prometheus_metrics_must_be_http_401(self):
        for phase, study, cases in [
            ("core", (404, None), (404, None)),
            ("study-core", WORKFLOWS, (401, None)),
            ("full", WORKFLOWS, (401, None)),
        ]:
            for exposed in ((200, None), (403, None), (503, None)):
                with self.subTest(phase=phase, anonymous_metrics_status=exposed[0]):
                    status, output = self.run_case(
                        phase,
                        [HEALTH, READY, study, cases],
                        metrics=exposed,
                    )
                    self.assertEqual(status, 1)
                    self.assertIn("BLOCKED anonymous_admin_metrics_denied", output)
                    self.assertNotIn("LIVE_RELEASE_GATE=PASS", output)

    def test_core_phase_passes_only_when_study_routes_not_deployed(self):
        status, output = self.run_case(
            "core", [HEALTH, READY, (404, None), (404, None)]
        )
        self.assertEqual(status, 0)
        self.assertIn("LIVE_CORE_GATE=PASS", output)
        self.assertIn("FULL_RELEASE_PRODUCTION=NOT_DEPLOYED", output)
        self.assertNotIn("LIVE_RELEASE_GATE=PASS", output)

    def test_study_core_phase_accepts_released_study_routes_without_claiming_full(self):
        status, output = self.run_case(
            "study-core", [HEALTH, READY, WORKFLOWS, (401, None)]
        )
        self.assertEqual(status, 0)
        self.assertIn("LIVE_STUDY_CORE_GATE=PASS", output)
        self.assertIn("FULL_RELEASE_PRODUCTION=NOT_DEPLOYED", output)
        self.assertNotIn("LIVE_RELEASE_GATE=PASS", output)

    def test_study_core_fails_when_study_routes_are_missing(self):
        status, output = self.run_case(
            "study-core", [HEALTH, READY, (404, None), (404, None)]
        )
        self.assertEqual(status, 1)
        self.assertIn("LIVE_STUDY-CORE_GATE=BLOCKED", output)

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

    def test_health_retries_cold_start_only_then_passes(self):
        with patch.object(
            probe, "probe", side_effect=[(503, None), (504, None), HEALTH]
        ) as request, patch.object(probe, "sleep") as sleeper:
            self.assertEqual(probe.probe_health_with_free_tier_cold_start(), HEALTH)
            self.assertEqual(request.call_count, 3)
            self.assertEqual(sleeper.call_count, 2)
            request.assert_any_call("/api/v1/health")

    def test_repeated_cold_start_503_does_not_claim_success(self):
        with patch.object(probe, "probe", return_value=(503, None)) as request, \
             patch.object(probe, "sleep") as sleeper:
            self.assertEqual(
                probe.probe_health_with_free_tier_cold_start(), (503, None)
            )
            self.assertEqual(request.call_count, 3)
            self.assertEqual(sleeper.call_count, 2)

    def test_health_transport_error_is_never_exposed_to_output(self):
        from urllib.error import URLError
        with patch.object(
            probe, "probe", side_effect=URLError("private internal details")
        ), patch.object(probe, "sleep"), redirect_stdout(StringIO()) as output:
            self.assertEqual(probe.main(["--expected-phase", "core"]), 1)
        self.assertNotIn("private internal details", output.getvalue())
        self.assertIn("LIVE_CORE_GATE=BLOCKED", output.getvalue())
    def test_no_phase_passes_if_database_not_ready(self):
        broken = (503, {"detail": "Service is not ready"})
        for phase, study, cases in [
            ("core", (404, None), (404, None)),
            ("study-core", WORKFLOWS, (401, None)),
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
