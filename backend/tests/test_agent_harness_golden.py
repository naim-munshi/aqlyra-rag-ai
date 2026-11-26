import json
from pathlib import Path

from app.services.agent_harness_service import validate_agent_input, AgentInputRejected


GOLDEN_PATH = Path(__file__).parents[1] / "evaluation" / "agent_harness_golden.json"


def test_agent_harness_golden_set_has_bounded_valid_cases():
    cases = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    assert len(cases) >= 5
    assert len({case["id"] for case in cases}) == len(cases)
    for case in cases:
        assert case["expected"] in {
            "answer_with_citations", "abstain", "input_guardrail_block"
        }
        assert isinstance(case["citation_required"], bool)
        assert 1 <= len(case["question"]) <= 2_000


def test_injection_golden_case_is_blocked_by_input_guardrail():
    cases = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    injection = next(case for case in cases if case["expected"] == "input_guardrail_block")
    try:
        validate_agent_input(injection["question"])
    except AgentInputRejected:
        return
    raise AssertionError("golden prompt-injection case must be blocked")
