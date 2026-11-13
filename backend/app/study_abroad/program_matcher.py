"""Genuine, inspectable study-program comparisons over explicitly stored facts.

This compares only matching GPA scales, test systems and currencies. Results
are NOT offers, admissions decisions, visa eligibility or acceptance odds.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from app.schemas.study_abroad import StudyApplicantFacts, ProgramRequirements

FRESH_DAYS = 45
JLPT_ORDER = {"N5": 1, "N4": 2, "N3": 3, "N2": 4, "N1": 5}


def _source_for(requirements: ProgramRequirements, reports: list[Any], now: datetime):
    if not requirements.evidence_report_id:
        return None
    for report in reports:
        if report.id != requirements.evidence_report_id:
            continue
        sources = report.sources if isinstance(report.sources, list) else []
        for source in sources:
            if isinstance(source, dict) and source.get("citation") == requirements.evidence_citation:
                when = report.searched_at
                if when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
                return {
                    "url": source.get("url"),
                    "searched_at": when.isoformat(),
                    "stale": (now - when).days > FRESH_DAYS,
                }
    return None


def matching_source_host(program_url: str, source_url: str) -> bool:
    """Only same host or direct parent/subdomain, not a lookalike suffix."""
    try:
        a = urlsplit(program_url)
        b = urlsplit(source_url)
        if (a.scheme != "https" or b.scheme != "https" or
                a.username or b.username or a.password or b.password or
                a.port not in (None, 443) or b.port not in (None, 443)):
            return False
        ah = (a.hostname or "").rstrip(".").lower()
        bh = (b.hostname or "").rstrip(".").lower()
        if not ah or not bh:
            return False
        return ah == bh or ah.endswith("." + bh) or bh.endswith("." + ah)
    except ValueError:
        return False


def assess_program(*, profile: StudyApplicantFacts, university: Any,
                   reports: list[Any], now: datetime) -> dict:
    req = ProgramRequirements.model_validate(university.requirements or {})
    criteria: list[dict[str, str]] = []

    def check(name: str, status: str, detail: str) -> None:
        criteria.append({"criterion": name, "status": status, "detail": detail})

    if req.minimum_gpa is None:
        check("gpa", "unknown", "No degree-specific minimum GPA entered.")
    elif profile.gpa is None:
        check("gpa", "unknown", "Enter your GPA and grading scale to compare.")
    elif profile.gpa_scale != req.gpa_scale:
        check("gpa", "unknown", "GPA grading scales differ; no automatic conversion is assumed.")
    elif profile.gpa >= req.minimum_gpa:
        check("gpa", "reported_match", f"Your {profile.gpa:g}/{profile.gpa_scale} meets the entered {req.minimum_gpa:g}/{req.gpa_scale} threshold.")
    else:
        check("gpa", "reported_gap", f"Your {profile.gpa:g}/{profile.gpa_scale} is below the entered {req.minimum_gpa:g}/{req.gpa_scale} minimum.")

    if req.minimum_language is None:
        check("language", "unknown", "No program-specific language requirement entered.")
    elif profile.language is None:
        check("language", "unknown", "No comparable test result recorded in your applicant profile.")
    elif profile.language.test != req.minimum_language.test:
        check("language", "unknown", "Tests differ; equivalence and exemptions require official confirmation.")
    elif profile.language.test == "JLPT":
        provided = JLPT_ORDER.get(profile.language.level or "", 0)
        required = JLPT_ORDER.get(req.minimum_language.level or "", 0)
        if provided >= required:
            check("language", "reported_match", f"Your JLPT {profile.language.level} meets the entered {req.minimum_language.level} level.")
        else:
            check("language", "reported_gap", f"Your JLPT {profile.language.level} is below the entered {req.minimum_language.level} level.")
    elif profile.language.score >= req.minimum_language.score:
        check("language", "reported_match", f"Your {profile.language.test} {profile.language.score:g} meets the entered {req.minimum_language.score:g} threshold.")
    else:
        check("language", "reported_gap", f"Your {profile.language.test} {profile.language.score:g} is below the entered {req.minimum_language.score:g} threshold.")

    if req.annual_tuition is None:
        check("tuition", "unknown", "Annual tuition has not been entered for this exact program.")
    elif profile.annual_budget is None:
        check("tuition", "unknown", "Enter your annual budget to compare tuition.")
    elif profile.currency != req.currency:
        check("tuition", "unknown", "Currencies differ; Aqlyra never invents exchange rates.")
    elif profile.annual_budget >= req.annual_tuition:
        check("tuition", "reported_match", f"Entered tuition {req.annual_tuition:g} {req.currency} is within your {profile.annual_budget:g} {profile.currency} annual budget; living and other costs are excluded.")
    else:
        check("tuition", "reported_gap", f"Entered tuition {req.annual_tuition:g} {req.currency} exceeds your {profile.annual_budget:g} {profile.currency} annual budget, before living expenses.")

    if not profile.transfer_requested:
        check("transfer", "unknown", "Transfer admissions were not requested in the applicant profile.")
    elif req.transfer_policy == "yes":
        check("transfer", "reported_match", "Transfer pathway is marked as available, but credit recognition and entry year remain unverified.")
    elif req.transfer_policy == "no":
        check("transfer", "reported_gap", "Transfer pathway is marked unavailable; confirm directly with the current university admissions office.")
    else:
        check("transfer", "unknown", "Transfer/credit recognition policy is not confirmed.")

    matched = sum(c["status"] == "reported_match" for c in criteria)
    gaps = sum(c["status"] == "reported_gap" for c in criteria)
    known = matched + gaps
    source = _source_for(req, reports, now)
    assessment = (
        "possible_gaps" if gaps
        else "potential_match_unverified" if known
        else "insufficient_evidence"
    )
    return {
        "university_id": university.id,
        "university_name": university.name,
        "program": university.program,
        "program_url": university.program_url,
        "assessment": assessment,
        "comparable_count": known,
        "matched_count": matched,
        "gap_count": gaps,
        "unknown_count": len(criteria) - known,
        "criteria": criteria,
        "provenance": "source_linked_unverified" if source else "self_reported_unverified",
        "evidence_url": source["url"] if source else None,
        "evidence_searched_at": source["searched_at"] if source else None,
        "source_stale": source["stale"] if source else True,
        "warning": (
            "Comparisons use applicant-entered scores and criteria; a citation link does not "
            "prove a program's entry rules. No admission, scholarship or visa outcome is guaranteed."
        ),
    }


def compare_programs(*, case: Any, universities: list[Any],
                     reports: list[Any], now: datetime | None = None) -> dict:
    stamp = now or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    profile = StudyApplicantFacts.model_validate(case.applicant_facts or {})
    results = [
        assess_program(profile=profile, university=u, reports=reports, now=stamp)
        for u in universities
    ]
    # Rank comparable evidence and potential gaps; never rank a blank card
    # as more promising than a program with at least one known criterion.
    results.sort(key=lambda p: (
        -p["comparable_count"],
        p["gap_count"],
        -p["matched_count"],
        p["university_name"].casefold(),
    ))
    return {
        "case_id": case.id,
        "profile": profile.model_dump(exclude_none=True),
        "programs": results,
        "checked_at": stamp.isoformat(),
        "disclaimer": (
            "This is a comparison of applicant-provided facts with entered thresholds, "
            "not admission probability. GPA conversions, language-test equivalences, "
            "living costs, credit recognition and official applicability require evidence."
        ),
    }
