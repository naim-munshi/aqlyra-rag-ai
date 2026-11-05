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


def draft_from_excerpt(excerpt: str) -> dict:
    """Find explicit values only; ambiguous phrasing produces no match."""
    if not isinstance(excerpt, str):
        return {}
    # Bounded untrusted text and no hidden HTML/script processing.
    excerpt = re.sub(r"<[^>]{0,400}>", " ", excerpt[:1600])
    found: dict = {}
    g = _GPA.search(excerpt)
    if g:
        value, scale = float(g.group(1)), int(g.group(2))
        if scale in _VALID_SCALES and value <= scale:
            found.update(minimum_gpa=value, gpa_scale=scale)
    lang = _IELTS.search(excerpt)
    if lang and float(lang.group(1)) <= 9:
        found["minimum_language"] = {"test": "IELTS", "score": float(lang.group(1))}
    else:
        lang = _TOEFL.search(excerpt)
        if lang and int(lang.group(1)) <= 120:
            found["minimum_language"] = {"test": "TOEFL_iBT", "score": int(lang.group(1))}
        else:
            lang = _JLPT.search(excerpt)
            if lang:
                found["minimum_language"] = {"test": "JLPT", "level": lang.group(1).upper()}
    tuition = _TUITION.search(excerpt)
    if tuition:
        amount = float(tuition.group(2).replace(",", ""))
        if 0 <= amount <= 200000000:
            found.update(annual_tuition=amount, currency=tuition.group(1).upper())
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
