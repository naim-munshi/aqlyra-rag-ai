"""Aggregate independently labeled grounding-verifier trials.

Scoring only. This module does not invoke an LLM or infer whether a citation
is truthful. Use adjudicated ground-truth labels and measured verifier calls;
mock verdicts are contract tests, not accuracy evidence.
"""
import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GroundingTrial:
    case_id: str
    language: str
    expected_supported: bool
    verifier_supported: bool | None
    verifier_latency_ms: float

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.language.strip():
            raise ValueError("Trial identity and language are required")
        if not isinstance(self.expected_supported, bool):
            raise ValueError("Ground-truth label must be boolean")
        if self.verifier_supported is not None and not isinstance(
            self.verifier_supported, bool,
        ):
            raise ValueError("Verifier verdict must be boolean or None")
        if (
            not math.isfinite(self.verifier_latency_ms)
            or self.verifier_latency_ms < 0
        ):
            raise ValueError("Verifier latency must be finite and nonnegative")


@dataclass(frozen=True, slots=True)
class GroundingQualitySummary:
    language: str
    cases: int
    supported_cases: int
    unsupported_cases: int
    false_accepts: int
    false_rejects: int
    verifier_errors: int
    accuracy_including_errors: float
    false_accept_rate: float
    false_reject_rate: float
    verifier_p50_ms: float
    verifier_p95_ms: float


def summarize_grounding_trials(
    trials: tuple[GroundingTrial, ...],
) -> tuple[GroundingQualitySummary, ...]:
    """Count unsafe unsupported-claim acceptance independently by language.

    Unknown/error verdicts count as incorrect on accuracy, not silently
    dropped. Rates use all gold-positive/gold-negative cases as denominators.
    A false-accept rate of zero on a tiny synthetic set proves nothing about
    production NLI/LLM accuracy.
    """
    if not trials:
        raise ValueError("At least one adjudicated trial is required")
    seen = set()
    by_language: dict[str, list[GroundingTrial]] = {}
    for trial in trials:
        key = (trial.language, trial.case_id)
        if key in seen:
            raise ValueError("Duplicate language/case_id trial")
        seen.add(key)
        by_language.setdefault(trial.language, []).append(trial)

    summaries: list[GroundingQualitySummary] = []
    for language in sorted(by_language):
        rows = by_language[language]
        total = len(rows)
        supported = sum(t.expected_supported for t in rows)
        unsupported = total - supported
        false_accepts = sum(
            not t.expected_supported and t.verifier_supported is True
            for t in rows
        )
        false_rejects = sum(
            t.expected_supported and t.verifier_supported is False
            for t in rows
        )
        errors = sum(t.verifier_supported is None for t in rows)
        correct = sum(
            t.verifier_supported is not None
            and t.verifier_supported is t.expected_supported
            for t in rows
        )
        latency = sorted(t.verifier_latency_ms for t in rows)

        def percentile(frac: float) -> float:
            index = max(0, math.ceil(frac * len(latency)) - 1)
            return round(latency[index], 3)

        summaries.append(GroundingQualitySummary(
            language=language,
            cases=total,
            supported_cases=supported,
            unsupported_cases=unsupported,
            false_accepts=false_accepts,
            false_rejects=false_rejects,
            verifier_errors=errors,
            accuracy_including_errors=correct / total,
            false_accept_rate=false_accepts / unsupported if unsupported else 0.0,
            false_reject_rate=false_rejects / supported if supported else 0.0,
            verifier_p50_ms=percentile(.5),
            verifier_p95_ms=percentile(.95),
        ))
    return tuple(summaries)
