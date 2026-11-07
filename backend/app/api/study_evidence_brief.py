"""Case-private evidence brief: actual stored research, program gaps and ready files.

Read-only, deterministic and provider-free. An evidence URL is a link to review,
never an assertion that its claims are correct for this applicant or intake.
"""
from datetime import datetime, timezone
import re
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.study_abroad import owned_case
from app.database.connection import get_db
from app.models.document import Document
from app.models.study_case import StudyCaseDocument, StudyResearchReport, StudyUniversity
from app.models.user import User
from app.services.web_research_service import safe_public_url
from app.study_abroad.advisor import build_study_advisor
from app.study_abroad.evidence_policy import authority_domains, matches_authority
from app.study_abroad.program_matcher import compare_programs, matching_source_host

router = APIRouter(prefix="/study-abroad", tags=["Study Abroad"])


def _public_link(raw: object) -> str | None:
    """Never reflect source URLs containing credentials or query tokens."""
    if not isinstance(raw, str) or safe_public_url(raw) is None:
        return None
    parsed = urlsplit(raw)
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        return None
    return urlunsplit(("https", parsed.netloc, parsed.path or "/", "", ""))


def _source_evidence(reports: list, stamp: datetime, destination: str) -> list[dict]:
    """One latest snapshot per topic; cap URLs, deduplicate and label uncertainty."""
    topics: set[str] = set()
    seen: set[str] = set()
    evidence: list[dict] = []
    for report in reports:
        if report.topic in topics:
            continue
        topics.add(report.topic)
        recorded = report.searched_at
        if recorded.tzinfo is None:
            recorded = recorded.replace(tzinfo=timezone.utc)
        age_days = max(0, (stamp - recorded).days)
        sources = report.sources if isinstance(report.sources, list) else []
        for raw in sources:
            if not isinstance(raw, dict):
                continue
            link = _public_link(raw.get("url"))
            if link is None or link in seen:
                continue
            citation = raw.get("citation")
            if not isinstance(citation, str) or re.fullmatch(r"\[W[1-9][0-9]*\]", citation, re.I) is None:
                continue
            seen.add(link)
            evidence.append({
                "topic": report.topic,
                "citation": citation[:12],
                "title": str(raw.get("title") or "Research source")[:160],
                "url": link,
                "source_type": (
                    "government_domain_unverified"
                    if matches_authority(link, authority_domains(destination))
                    else "external_source_unverified"
                ),
                "searched_at": recorded.isoformat(),
                "age_days": age_days,
                "stale": age_days > 45,
                "verification_status": "needs_independent_review",
            })
            if len(evidence) >= 12:
                return evidence
    return evidence


@router.get("/cases/{case_id}/evidence-brief")
def get_study_evidence_brief(
    case_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """One read-only view of case-local fit, research and linked-file *status*.

    Never reads document text, sends anything to the LLM/web, or changes state.
    Does not include other journeys, user notes, emails, or signed storage URLs.
    """
    case = owned_case(db, str(user.id), case_id)
    schools = list(db.scalars(
        select(StudyUniversity).where(StudyUniversity.case_id == case.id)
        .order_by(StudyUniversity.created_at.desc()).limit(40)
    ).all())
    reports = list(db.scalars(
        select(StudyResearchReport).where(StudyResearchReport.case_id == case.id)
        .order_by(StudyResearchReport.searched_at.desc()).limit(50)
    ).all())
    # Join to the actual owner and READY status: linked IDs alone do not prove
    # that a document is still present, processed or owned by this caller.
    ready_links = list(db.execute(
        select(StudyCaseDocument.checklist_key, Document.id)
        .join(Document, Document.id == StudyCaseDocument.document_id)
        .where(
            StudyCaseDocument.case_id == case.id,
            Document.user_id == str(user.id),
            Document.status == "ready",
        ).limit(40)
    ).all())
    stamp = datetime.now(timezone.utc)
    matches = compare_programs(
        case=case, universities=schools, reports=reports, now=stamp,
    )
    advisor = build_study_advisor(
        case=case, universities=schools, reports=reports,
        linked_document_count=len(ready_links), now=stamp,
    )
    evidence = _source_evidence(reports, stamp, case.destination_country)
    pending = [
        {"key": key, "title": str(value.get("title") or key)[:140],
         "state": str(value.get("state") or "needs_verification")}
        for key, value in (case.checklist or {}).items()
        if isinstance(value, dict)
        and value.get("state") not in ("reviewed", "not_applicable")
    ][:20]
    programs = []
    for item in matches["programs"][:10]:
        school = next((s for s in schools if s.id == item["university_id"]), None)
        # Do not forward user-saved URL query secrets.
        program_url = _public_link(school.program_url) if school else None
        source_url = _public_link(item["evidence_url"])
        if source_url and (program_url is None or not matching_source_host(program_url, source_url)):
            source_url = None
        programs.append({
            "university_id": item["university_id"],
            "university_name": item["university_name"],
            "program": item["program"],
            "program_url": program_url,
            "assessment": item["assessment"],
            "gap_count": item["gap_count"],
            "matched_count": item["matched_count"],
            "unknown_count": item["unknown_count"],
            "needs_review": [
                {"criterion": c["criterion"], "status": c["status"],
                 "detail": c["detail"]}
                for c in item["criteria"] if c["status"] != "reported_match"
            ],
            "evidence_url": source_url,
            "source_stale": item["source_stale"] or not source_url,
            "provenance": (
                "source_linked_unverified"
                if source_url else "self_reported_unverified"
            ),
        })

    return {
        "case_id": case.id,
        "generated_at": stamp.isoformat(),
        "status": "planning_snapshot_unverified",
        "summary": {
            "shortlisted_programs": len(matches["programs"]),
            "displayed_programs": len(programs),
            "programs_with_reported_gaps": sum(
                p["gap_count"] > 0 for p in matches["programs"]
            ),
            "unresolved_program_criteria": sum(
                p["unknown_count"] for p in matches["programs"]
            ),
            "linked_ready_documents": len(ready_links),
            "outstanding_self_review_items": len(pending),
            "saved_research_topics": len(advisor["research_freshness"]),
            "stale_research_topics": sum(
                report["stale"] for report in advisor["research_freshness"]
            ),
        },
        "documents": {
            "ready_count": len(ready_links),
            "linked_categories": sorted({category for category, _ in ready_links}),
            "outstanding_self_review": pending,
            "note": "Only the presence of owner-linked, processed files was checked; their contents and authenticity were not inspected.",
        },
        "programs": programs,
        "saved_source_links": evidence,
        "research_freshness": advisor["research_freshness"],
        "next_actions": advisor["next_actions"],
        "privacy": {
            "external_requests_made": 0,
            "document_text_accessed": False,
            "document_excerpts_shared": False,
        },
        "disclaimer": (
            "Saved evidence is not independently verified. GPA/language comparisons "
            "use user-entered criteria, and linked files are not automatically checked. "
            "Reconfirm program requirements, source applicability, deadlines and "
            "document authenticity with official providers. This is not an admission "
            "probability, visa decision or application submission."
        ),
    }
