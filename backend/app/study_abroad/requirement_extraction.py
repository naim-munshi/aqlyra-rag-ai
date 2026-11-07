"""Conservative extraction of *draft* academic facts from cited first-party snippets.

No LLM interpretation is allowed to silently become a confirmed requirement.
The owner explicitly reviews and saves suggestions. A search snippet does not
establish the exact intake, course, admissions route, or current publication.
"""
from datetime import datetime, timezone
import re
from typing import Any

from app.study_abroad.program_matcher import matching_source_host, FRESH_DAYS

_GPA = re.compile(
    r"\b(?:minimum|at\s+least|required)\s+(?:cumulative\s+)?GPA\s*"
    r"(?:of\s*|:\s*|>=\s*)?([0-9]+(?:\.[0-9]{1,2})?)\s*"
    r"(?:/|out\s+of|on\s+a?)\s*(4|5|10|100)(?:\.0)?\b", re.I,
)
_IELTS = re.compile(
    r"\b(?:minimum|required|at\s+least)\s+(?:overall\s+)?IELTS"
    r"(?:\s+academic)?(?:\s+score)?\s*(?:of|:)?\s*([0-9](?:\.[0-9])?)\b", re.I,
)
_TOEFL = re.compile(
    r"\b(?:minimum|required|at\s+least)\s+TOEFL\s*(?:iBT)?"
    r"(?:\s+score)?\s*(?:of|:)?\s*(\d{2,3})\b", re.I,
)
_JLPT = re.compile(
    r"\b(?:minimum|required|at\s+least)\s+JLPT\s*(N[1-5])\b", re.I,
)
_TUITION = re.compile(
    r"\b(?:annual\s+tuition|tuition\s+per\s+year|yearly\s+tuition)"
    r"(?:\s+fees?)?\s*(?:is|:)?\s*"
    r"(JPY|USD|EUR|GBP|AUD|CAD|BDT)\s*([\d,]+(?:\.\d{1,2})?)\b", re.I,
)
_VALID_SCALES = (4, 5, 10, 100)


def _nonbinding_context(excerpt: str, match: re.Match[str]) -> bool:
    """An apparent threshold negated or marked hypothetical is not evidence.

    Evaluate only its local clause: a separate sentence about waivers must not
    invalidate a clearly stated requirement elsewhere in the same snippet.
    """
    before = re.split(r"[.!?;\\n]", excerpt[max(0, match.start() - 90):match.start()])[-1]
    after = re.split(r"[.!?;\\n]", excerpt[match.end():match.end() + 90])[0]
    if re.search(
        r"\\b(?:no|not|without|waived|waiver|optional|exempt)\\b"
        r"(?:[\\s,:-]+[A-Za-z0-9-]+){0,5}\\s*$",
        before, re.I,
    ):
        return True
    if re.match(
        r"\\s*(?:(?:is|are|was|were|will be|may be|has been)\\s+)?"
        r"(?:not\\b|no\\s+longer\\b|waived\\b|optional\\b|exempt\\b)",
        after, re.I,
    ):
        return True
    return bool(re.search(r"\\b(?:hypothetical|illustrative|not applicable)\\b", after, re.I))


def _unambiguous_matches(excerpt: str, pattern: re.Pattern[str], converter):
    """Skip contradictory thresholds instead of silently picking the first."""
    values = {
        value
        for match in pattern.finditer(excerpt)
        if not _nonbinding_context(excerpt, match)
        for value in [converter(match)]
        if value is not None
    }
    return next(iter(values)) if len(values) == 1 else None


def draft_from_excerpt(excerpt: str) -> dict:
    """Produce only unambiguous, non-negated draft facts for manual review."""
    if not isinstance(excerpt, str):
        return {}
    excerpt = re.sub(r"<[^>]{0,400}>", " ", excerpt[:1600])
    found: dict = {}

    def parse_gpa(match: re.Match[str]):
        score, scale = float(match.group(1)), int(match.group(2))
        return (score, scale) if scale in _VALID_SCALES and score <= scale else None

    gpa = _unambiguous_matches(excerpt, _GPA, parse_gpa)
    if gpa is not None:
        found.update(minimum_gpa=gpa[0], gpa_scale=gpa[1])

    languages = {
        ("IELTS", float(m.group(1)))
        for m in _IELTS.finditer(excerpt)
        if float(m.group(1)) <= 9 and not _nonbinding_context(excerpt, m)
    }
    languages.update(
        ("TOEFL_iBT", int(m.group(1)))
        for m in _TOEFL.finditer(excerpt)
        if int(m.group(1)) <= 120 and not _nonbinding_context(excerpt, m)
    )
    languages.update(
        ("JLPT", m.group(1).upper())
        for m in _JLPT.finditer(excerpt)
        if not _nonbinding_context(excerpt, m)
    )
    # Multiple distinct test paths/thresholds must be reviewed on the full
    # page; one form field cannot safely capture such alternatives.
    if len(languages) == 1:
        test, value = next(iter(languages))
        found["minimum_language"] = (
            {"test": "JLPT", "level": value}
            if test == "JLPT" else {"test": test, "score": value}
        )

    def parse_tuition(match: re.Match[str]):
        amount = float(match.group(2).replace(",", ""))
        return (match.group(1).upper(), amount) if 0 <= amount <= 200000000 else None

    tuition = _unambiguous_matches(excerpt, _TUITION, parse_tuition)
    if tuition is not None:
        found.update(annual_tuition=tuition[1], currency=tuition[0])
    return found


def draft_university_requirements(
    *, university: Any, reports: list[Any],
    now: datetime | None = None,
) -> list[dict]:
    """Never persist suggestions. Require exact saved first-party source URL."""
    stamp = now or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    drafts: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for report in reports:
        sources = report.sources if isinstance(report.sources, list) else []
        for source in sources:
            if not isinstance(source, dict):
                continue
            url, citation = source.get("url"), source.get("citation")
            if not isinstance(url, str) or not isinstance(citation, str):
                continue
            if not matching_source_host(university.program_url, url):
                continue
            facts = draft_from_excerpt(source.get("excerpt", ""))
            if not facts or (report.id, citation) in seen:
                continue
            seen.add((report.id, citation))
            when = report.searched_at
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            drafts.append({
                "report_id": report.id,
                "citation": citation,
                "source_url": url,
                "searched_at": when.isoformat(),
                "stale": (stamp - when).days > FRESH_DAYS,
                "suggested_facts": facts,
                "status": "extracted_from_snippet_review_required",
                "note": (
                    "Detected text in a saved source excerpt is not verified as "
                    "applicable to this program, intake or transfer category. "
                    "Review the full first-party page before saving."
                ),
            })
            if len(drafts) >= 12:
                return drafts
    return drafts
