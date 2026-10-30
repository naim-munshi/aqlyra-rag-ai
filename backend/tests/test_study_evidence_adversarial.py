"""Regression checks for visa/admissions research citation coverage bypasses.

These checks are structural only; they do not assert that a linked
government page semantically proves the model's proposed legal claim.
"""
import pytest

from app.study_abroad.evidence_policy import (
    UnsupportedStudyClaims,
    validate_study_citation_coverage,
)


SOURCES = [
    {"citation": "[W1]"},
    {"citation": "[W2]"},
]


def test_short_markdown_heading_and_cited_claims_are_valid():
    validate_study_citation_coverage(
        "## Visa documents\n\n"
        "The authority lists conditional evidence rules [W1].\n\n"
        "- An appointment might be required at a mission [W2].",
        SOURCES,
    )


@pytest.mark.parametrize("unreferenced", [
    # Headings must not be a backdoor for unsupported immigration claims.
    "## Students from all countries automatically receive permanent visas",
    "### No applicant ever needs to submit proof of funds",
    # A colon is punctuation, not an evidence exception.
    "All applicants will always receive their visa automatically:",
    "No applicant needs any financial documents whatsoever:",
    # A line styled as a list or a table still requires sources.
    "- All students automatically obtain unrestricted employment rights",
    "| Every student receives unlimited work authorization |",
])
def test_unsupported_visa_assertions_cannot_hide_behind_formatting(unreferenced):
    response = unreferenced + (
        "\n\nOfficial authorities set conditional admission rules [W1]."
    )
    with pytest.raises(UnsupportedStudyClaims):
        validate_study_citation_coverage(response, SOURCES)


def test_case_insensitive_citations_still_match_official_source_ids():
    validate_study_citation_coverage(
        "Official requirements depend on applicant circumstances [w1].",
        [{"citation": "[w1]"}],
    )


@pytest.mark.parametrize("untrusted", [
    {"citation": "[W1]not-a-citation"},
    {"citation": "W1"},
    {"citation": "[W999]"},
])
def test_malformed_or_unlisted_citation_labels_fail_closed(untrusted):
    with pytest.raises(UnsupportedStudyClaims):
        validate_study_citation_coverage(
            "The government lists required documents [W1].",
            [untrusted],
        )
