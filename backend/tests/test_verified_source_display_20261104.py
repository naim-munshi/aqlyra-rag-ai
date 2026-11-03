"""Citation UX regression: show only evidence the factual answer actually cited."""

from types import SimpleNamespace

from app.services.auto_web_research_service import cited_web_answer


def test_short_verified_answer_links_only_its_primary_source():
    sources = [
        SimpleNamespace(citation="[W1]", title="Official administration", url="https://www.whitehouse.gov/administration/"),
        SimpleNamespace(citation="[W2]", title="Unrelated election guide", url="https://example.org/guide"),
        SimpleNamespace(citation="[W3]", title="Unrelated article", url="https://example.org/article"),
    ]
    result = cited_web_answer("Verified incumbent, from an official source [W1].", sources)
    assert "whitehouse.gov/administration" in result
    assert "example.org/guide" not in result
    assert "example.org/article" not in result
    assert "[W1]" in result
    assert "**Web sources**" in result


def test_multiple_cited_sources_remain_available():
    sources = [
        SimpleNamespace(citation="[W1]", title="Official", url="https://example.org/one"),
        SimpleNamespace(citation="[W2]", title="Corroboration", url="https://example.net/two"),
    ]
    result = cited_web_answer("Supported by two documents [W2] [W1].", sources)
    assert "example.org/one" in result
    assert "example.net/two" in result


def test_zero_citations_never_invents_a_source_section():
    sources = [
        SimpleNamespace(citation="[W1]", title="Uncited", url="https://example.com/unrelated"),
    ]
    result = cited_web_answer("No supported answer.", sources)
    assert result == "No supported answer."
