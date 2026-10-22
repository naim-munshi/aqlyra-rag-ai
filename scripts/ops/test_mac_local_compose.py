"""Reject unsafe local-service published ports and production SMTP usage."""
import copy
import unittest

from check_mac_local_compose import audit_local


def safe_config():
    def port(target: int):
        return [{"host_ip": "127.0.0.1", "target": target, "protocol": "tcp"}]

    return {
        "frontend": {"ports": port(3000)},
        "backend": {
            "ports": port(8000),
            "environment": {
                "APP_ENV": "development",
                "SMTP_HOST": "mailpit",
                "SMTP_PORT": "1025",
                "SMTP_USE_SSL": "false",
                "SMTP_STARTTLS": "false",
                "EMAIL_VERIFICATION_REQUIRED": "true",
            },
            "depends_on": {"mailpit": {"condition": "service_started"}},
        },
        "postgres": {"ports": port(5432)},
        "mailpit": {"ports": port(8025)},
        "redis": {},
    }


class MacLocalComposeContractTest(unittest.TestCase):
    def setUp(self):
        self.services = copy.deepcopy(safe_config())

    def test_approved_local_topology(self):
        self.assertEqual(audit_local(self.services), [])

    def test_frontend_must_not_be_public(self):
        self.services["frontend"]["ports"][0]["host_ip"] = "0.0.0.0"
        self.assertTrue(audit_local(self.services))

    def test_database_must_not_be_public(self):
        self.services["postgres"]["ports"][0]["host_ip"] = ""
        self.assertTrue(audit_local(self.services))

    def test_smtp_sink_must_not_publish_smtp(self):
        self.services["mailpit"]["ports"].append({
            "host_ip": "127.0.0.1", "target": 1025, "protocol": "tcp"
        })
        self.assertTrue(audit_local(self.services))

    def test_redis_must_be_private(self):
        self.services["redis"]["ports"] = [{"target": 6379}]
        self.assertTrue(audit_local(self.services))

    def test_plain_smtp_never_allowed_in_production_mode(self):
        self.services["backend"]["environment"]["APP_ENV"] = "production"
        self.assertTrue(audit_local(self.services))

    def test_mailpit_dependency_is_required(self):
        self.services["backend"]["depends_on"] = {}
        self.assertTrue(audit_local(self.services))


if __name__ == "__main__":
    unittest.main()
