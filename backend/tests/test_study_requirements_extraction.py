"""First-party source snippets may propose facts but cannot auto-change admissions."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.study_abroad.requirement_extraction import (
    draft_from_excerpt, draft_university_requirements,
)


def test_explicit_sourced_thresholds_extract_with_no_guesswork():
    facts = draft_from_excerpt(
        "Minimum GPA of 3.20/4.0. Minimum IELTS 6.5. "
        "Annual tuition: JPY 1,200,000 for this sample program."
    )
    assert facts == {
        "minimum_gpa": 3.2,
        "gpa_scale": 4,
        "minimum_language": {"test": "IELTS", "score": 6.5},
        "annual_tuition": 1200000.0,
        "currency": "JPY",
    }
    assert draft_from_excerpt(
        "We welcome all students. IELTS scores and GPA may be reviewed."
    ) == {}
    assert draft_from_excerpt(
        "Minimum GPA 6/4. Minimum IELTS 12. Annual tuition USD 300,000,000."
    ) == {}
    assert draft_from_excerpt(
        "minimum JLPT N2 is required for this Japanese-language degree."
    ) == {"minimum_language": {"test": "JLPT", "level": "N2"}}


def test_only_saved_same_university_citations_can_propose_editable_facts():
    now = datetime(2027, 1, 1, tzinfo=timezone.utc)
    school = SimpleNamespace(
        id="school-1", program_url="https://admissions.example.edu/course"
    )
    report = SimpleNamespace(
        id="report-a", searched_at=now - timedelta(days=8),
        sources=[
            {
                "url": "https://admissions.example.edu/transfer",
                "citation": "[W1]",
                "excerpt": "Minimum GPA of 3.0/4.0. Minimum IELTS 6.0.",
            },
            {
                "url": "https://admissions.example.edu.attacker.com/forgery",
                "citation": "[W2]",
                "excerpt": "Minimum GPA of 1.0/4.0.",
            },
            {
                "url": "https://blog.example.net/opinion",
                "citation": "[W3]",
                "excerpt": "Annual tuition: EUR 1000.",
            },
        ],
    )
    drafts = draft_university_requirements(
        university=school, reports=[report], now=now
    )
    assert len(drafts) == 1
    assert drafts[0]["citation"] == "[W1]"
    assert drafts[0]["source_url"] == "https://admissions.example.edu/transfer"
    assert drafts[0]["suggested_facts"]["minimum_gpa"] == 3.0
    assert drafts[0]["status"] == "extracted_from_snippet_review_required"
    assert not drafts[0]["stale"]
    old = draft_university_requirements(
        university=school, reports=[report],
        now=now + timedelta(days=50),
    )
    assert old[0]["stale"]
