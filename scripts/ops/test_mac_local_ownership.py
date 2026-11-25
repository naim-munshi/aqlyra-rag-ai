"""Offline tests for non-destructive Mac container ownership preflight."""
import unittest
from unittest.mock import Mock

from check_mac_local_ownership import (
    find_ownership_conflicts,
)


class MacLocalOwnershipTest(unittest.TestCase):
    def test_fresh_project_without_containers_passes(self):
        getter = Mock(side_effect=AssertionError("must not inspect absent names"))
        assert find_ownership_conflicts(
            "aqlyra-rag-ai-live", set(), getter
        ) == []
        getter.assert_not_called()

    def test_existing_matching_project_can_restart(self):
        assert find_ownership_conflicts(
            "aqlyra-rag-ai",
            {"aqlyra-postgres", "aqlyra-backend"},
            lambda name: "aqlyra-rag-ai",
        ) == []

    def test_existing_other_worktree_refuses_start(self):
        failures = find_ownership_conflicts(
            "aqlyra-rag-ai-live",
            {"aqlyra-postgres", "aqlyra-redis", "other-project"},
            lambda name: "aqlyra-rag-ai",
        )
        assert len(failures) == 2
        assert "aqlyra-postgres" in failures[0]

    def test_unlabelled_existing_container_refuses_start(self):
        failures = find_ownership_conflicts(
            "aqlyra-rag-ai-live",
            {"aqlyra-postgres"},
            lambda name: "<no value>",
        )
        assert len(failures) == 1

    def test_missing_expected_project_refuses_start(self):
        failures = find_ownership_conflicts(
            "", set(), lambda name: "aqlyra-rag-ai"
        )
        assert failures == ["Compose project name is missing"]

    def test_unrelated_containers_are_ignored(self):
        getter = Mock(side_effect=AssertionError("must not inspect unrelated"))
        assert find_ownership_conflicts(
            "aqlyra-rag-ai-live", {"unrelated-redis"}, getter
        ) == []
        getter.assert_not_called()


if __name__ == "__main__":
    unittest.main()
