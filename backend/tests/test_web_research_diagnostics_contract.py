"""Non-secret Web Research diagnostic contract."""
from pathlib import Path


def test_web_stage_diagnostics_never_log_user_query_or_page_text():
    source = Path(__file__).resolve().parents[1].joinpath(
        "app", "services", "web_research_service.py"
    ).read_text(encoding="utf-8")
    for stage in (
        "search_no_candidates",
        "extract_no_readable_pages",
        "invalid_citations",
        "unapproved_generated_link",
    ):
        assert "stage=" + stage in source
    for forbidden in (
        "logger.warning(question",
        "logger.warning(text",
        "logger.warning(sources",
        "logger.warning(excerpt",
    ):
        assert forbidden not in source
