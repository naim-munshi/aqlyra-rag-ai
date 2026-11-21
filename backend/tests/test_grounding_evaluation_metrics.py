import pytest

from app.rag.grounding_evaluation import (
    GroundingTrial,
    summarize_grounding_trials,
)


def test_adjudicated_grounding_counts_unsafe_false_accepts_and_errors_by_language():
    # Synthetic verdicts test scoring only, not real LLM semantic accuracy.
    rows = (
        GroundingTrial("ja-ok", "ja", True, True, 11),
        GroundingTrial("ja-hallucinated-number", "ja", False, True, 12),
        GroundingTrial("ja-negation", "ja", False, False, 8),
        GroundingTrial("bn-correct-fact", "bn", True, True, 9),
        GroundingTrial("bn-missed-fact", "bn", True, False, 13),
        GroundingTrial("bn-verifier-error", "bn", False, None, 20),
    )
    summary = summarize_grounding_trials(rows)
    assert [item.language for item in summary] == ["bn", "ja"]
    bengali, japanese = summary
    assert bengali.cases == 3
    assert bengali.supported_cases == 2
    assert bengali.unsupported_cases == 1
    assert bengali.false_accepts == 0
    assert bengali.false_rejects == 1
    assert bengali.verifier_errors == 1
    assert bengali.accuracy_including_errors == pytest.approx(1/3)
    assert bengali.false_reject_rate == pytest.approx(.5)
    assert bengali.verifier_p95_ms == 20
    assert japanese.false_accepts == 1
    assert japanese.false_accept_rate == pytest.approx(.5)
    assert japanese.accuracy_including_errors == pytest.approx(2/3)
    assert japanese.verifier_p50_ms == 11


@pytest.mark.parametrize("bad_latency", [-1, float("nan"), float("inf")])
def test_adjudication_rejects_invalid_timings(bad_latency):
    with pytest.raises(ValueError, match="finite and nonnegative"):
        GroundingTrial("one", "en", True, True, bad_latency)


def test_adjudication_rejects_duplicate_cases_and_unknown_labels():
    item = GroundingTrial("duplicate", "en", True, False, 5)
    with pytest.raises(ValueError, match="Duplicate"):
        summarize_grounding_trials((item, item))
    with pytest.raises(ValueError, match="At least one"):
        summarize_grounding_trials(())
    with pytest.raises(ValueError, match="boolean or None"):
        GroundingTrial("wrong", "en", True, "SUPPORTED", 5)
