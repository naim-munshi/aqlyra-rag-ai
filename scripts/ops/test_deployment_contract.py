"""Offline regression checks against accidental public deployment exposure."""
import copy
import unittest

from deployment_contract import audit_services


def valid_config():
    app_security = {
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
    }
    volume = lambda source, target: {
        "type": "volume", "source": source, "target": target
    }
    return {
        "backend": {
            **app_security,
            "ports": [{"host_ip": "127.0.0.1", "target": 8000, "protocol": "tcp"}],
            "volumes": [volume("uploads", "/app/uploads")],
        },
        "postgres": {
            "ports": [{"host_ip": "127.0.0.1", "target": 5432, "protocol": "tcp"}],
            "volumes": [volume("postgres_data", "/var/lib/postgresql/data")],
        },
        "redis": {},
        "voice-worker": {**app_security, "volumes": [volume("uploads", "/app/uploads")]},
        "alert-worker": {**app_security},
        "frontend": {**app_security},
        "caddy": {
            "ports": [
                {"target": 80, "protocol": "tcp"},
                {"target": 443, "protocol": "tcp"},
                {"target": 443, "protocol": "udp"},
            ],
            "volumes": [volume("caddy_data", "/data"), volume("caddy_config", "/config")],
        },
    }


class DeploymentContractTests(unittest.TestCase):
    def setUp(self):
        self.services = copy.deepcopy(valid_config())

    def assert_rejected(self, text):
        findings = audit_services(self.services)
        self.assertTrue(any(text in finding for finding in findings), findings)

    def test_safe_topology(self):
        self.assertEqual(audit_services(self.services), [])

    def test_backend_cannot_bind_public_ip(self):
        self.services["backend"]["ports"][0]["host_ip"] = "0.0.0.0"
        self.assert_rejected("loopback")

    def test_database_cannot_bind_public_ip(self):
        self.services["postgres"]["ports"][0]["host_ip"] = ""
        self.assert_rejected("loopback")

    def test_redis_cannot_publish(self):
        self.services["redis"]["ports"] = [{"target": 6379}]
        self.assert_rejected("redis: must not publish")

    def test_frontend_cannot_publish(self):
        self.services["frontend"]["ports"] = [{"target": 3000}]
        self.assert_rejected("frontend: must not publish")

    def test_container_capabilities_required(self):
        self.services["voice-worker"]["cap_drop"] = []
        self.assert_rejected("drop ALL")

    def test_privilege_escalation_rejected(self):
        self.services["frontend"]["security_opt"] = []
        self.assert_rejected("no-new-privileges")

    def test_privileged_database_rejected(self):
        self.services["postgres"]["privileged"] = True
        self.assert_rejected("privileged container")

    def test_host_network_rejected(self):
        self.services["backend"]["network_mode"] = "host"
        self.assert_rejected("host networking")

    def test_upload_volumes_must_match(self):
        self.services["voice-worker"]["volumes"][0]["source"] = "wrong"
        self.assert_rejected("share the uploads volume")

    def test_database_requires_volume(self):
        self.services["postgres"]["volumes"] = []
        self.assert_rejected("persistent named volume")

    def test_caddy_cannot_publish_backend_port(self):
        self.services["caddy"]["ports"].append({"target": 8000})
        self.assert_rejected("caddy")

    def test_missing_service_is_rejected(self):
        self.services.pop("alert-worker")
        self.assert_rejected("required service missing")


if __name__ == "__main__":
    unittest.main()
