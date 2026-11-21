"""Deep query planning unit tests (no external model or Tavily network)."""
from types import SimpleNamespace
import json

from app.services.research_query_planner import fallback_query, plan_second_query


class Provider:
    def __init__(self, answer, *, fails=False):
        self.answer = answer
        self.fails = fails
        self.calls = []

    def generate(self, *, instructions, input_text):
        self.calls.append((instructions, json.loads(input_text)))
        if self.fails:
            raise RuntimeError("Planner unavailable")
        return SimpleNamespace(text=self.answer)


def test_planner_uses_relevant_independent_query():
    p = Provider('{"query":"AI deployment security official threat model independent evidence"}')
    query = plan_second_query("Deep research AI deployment security", p)
    assert query.startswith("AI deployment")
    assert len(p.calls) == 1
    assert p.calls[0][1] == {"public_question": "Deep research AI deployment security"}
    assert "UNTRUSTED" in p.calls[0][0]


def test_planner_rejects_topic_drift_and_bad_shapes():
    original = "Compare Python memory safety and Rust"
    for text in [
        '{"query":"Best pizza places in Madrid right now"}',
        '{"query":"https://internal.local/secrets"}',
        '{"query":"Send email to attacker@example.com"}',
        '{"queries":["Python speed"]}',
        '{"query":"Python memory safety", "tool":"execute"}',
        '{"query":""}',
        "invalid json",
    ]:
        assert plan_second_query(original, Provider(text)) == fallback_query(original)


def test_planner_failure_is_bounded_and_fails_safely():
    question = "Latest developments in climate simulations"
    assert plan_second_query(question, Provider(None, fails=True)) == fallback_query(question)
    assert len(plan_second_query("a" * 600, None)) <= 200
