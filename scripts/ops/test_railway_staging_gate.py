"""Unit checks for the Railway staging fail-closed gate. Pure offline fixtures."""
import unittest

import railway_staging_gate as gate

SHA = "b5fa5666790b711d081f250bf1c44c8c6c22b8d8"


def inventory():
    def service(name):
        return {"name": name, "state": "live",
                "latestDeployment": {"status": "SUCCESS"},
                "config": {"source": {}}, "volumes": [],
                "domains": {"serviceDomains": [], "customDomains": []},
                "tcpProxies": [], "variableNames": []}
    postgres = service("aqlyra-postgres-pgvector")
    postgres["config"]["source"] = {"image": "pgvector/pgvector:pg16"}
    postgres["volumes"] = [{"mountPath": "/var/lib/postgresql/data", "state": "live"}]
    backend = service("aqlyra-backend")
    backend["config"]["source"] = {"repo": gate.EXPECTED_REPO, "branch": gate.CORE_BRANCH, "commitSha": SHA}
    backend["volumes"] = [{"mountPath": "/app/uploads", "state": "live"}]
    backend["variableNames"] = sorted(gate.REQUIRED_BACKEND_VARIABLE_NAMES)
    frontend = service("aqlyra-frontend")
    frontend["config"]["source"] = {"repo": gate.EXPECTED_REPO, "branch": gate.CORE_BRANCH, "commitSha": SHA}
    frontend["variableNames"] = sorted(gate.REQUIRED_FRONTEND_VARIABLE_NAMES)
    frontend["domains"]["serviceDomains"] = [{"domain": "example.up.railway.app"}]
    return {"storageSecurity": {"backendUploadRWAsUID10001Verified": True, "backendRunningAsRoot": False},
            "project": {"name": "Aqlyra-Staging"},
            "environment": {"name": "staging"}, "staged": None,
            "services": [postgres, backend, frontend, service("aqlyra-redis")]}


class TestRailwayStagingGate(unittest.TestCase):
    def test_healthy_synthetic_inventory_passes_structural_gate_only(self):
        self.assertEqual(gate.assess(inventory(), SHA), [])

    def test_nonroot_volume_write_proof_required(self):
        data = inventory()
        data.pop("storageSecurity")
        self.assertTrue(any("UID 10001" in e for e in gate.assess(data, SHA)))

    def test_root_runtime_rejected(self):
        data = inventory()
        data["storageSecurity"]["backendRunningAsRoot"] = True
        self.assertTrue(any("root runtime" in e for e in gate.assess(data, SHA)))

    def test_pending_changes_fail(self):
        data = inventory()
        data["staged"] = {"status": "STAGED"}
        self.assertTrue(any("Pending" in e for e in gate.assess(data, SHA)))

    def test_no_redis_fails(self):
        data = inventory()
        data["services"] = [x for x in data["services"] if x["name"] != "aqlyra-redis"]
        self.assertTrue(any("aqlyra-redis" in e for e in gate.assess(data, SHA)))

    def test_ephemeral_uploads_fail(self):
        data = inventory()
        data["services"][1]["volumes"] = []
        self.assertTrue(any("/app/uploads" in e for e in gate.assess(data, SHA)))

    def test_exposed_database_fails(self):
        data = inventory()
        data["services"][0]["tcpProxies"] = [{"endpoint": "public:5432"}]
        self.assertTrue(any("public TCP proxy" in e for e in gate.assess(data, SHA)))

    def test_mismatched_revision_fails(self):
        data = inventory()
        self.assertTrue(any("pinned" in e for e in gate.assess(data, "a" * 40)))

    def test_missing_secret_name_fails(self):
        data = inventory()
        data["services"][1]["variableNames"].remove("SECRET_KEY")
        self.assertTrue(any("SECRET_KEY" in e for e in gate.assess(data, SHA)))

    def test_fail_closes_on_uncommitted_resources(self):
        data = inventory()
        data["services"][0]["state"] = "staged-create"
        data["services"][0]["latestDeployment"] = None
        errors = gate.assess(data, SHA)
        self.assertTrue(any("not live" in e for e in errors))
        self.assertTrue(any("SUCCESS" in e for e in errors))

    def test_unscoped_repository_fails(self):
        data = inventory()
        data["services"][2]["config"]["source"]["repo"] = "naim-munshi/aqlyrax"
        self.assertTrue(any("source" in e for e in gate.assess(data, SHA)))


if __name__ == "__main__":
    unittest.main()
