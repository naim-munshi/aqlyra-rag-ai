"""Opt-in verified-host study program evidence refresh, without auto-accepting claims.

A source host matches the student's saved shortlisted URL; this is not a
government validation or proof of exact intake applicability.
"""
from datetime import timezone
import re
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.study_abroad import owned_case
from app.core.rate_limit import limit_rag_request
from app.database.connection import get_db
from app.llms.types import LLMError
from app.models.study_case import StudyUniversity, StudyResearchReport
from app.models.user import User
from app.schemas.study_abroad import StudyResearchResponse
from app.services.web_research_service import (
    research_web, safe_public_url, WebResearchUnavailable,
    WebResearchEvidenceError,
)
from app.study_abroad.program_matcher import matching_source_host
from app.study_abroad.evidence_policy import (
    validate_study_citation_coverage, UnsupportedStudyClaims,
)
from app.study_abroad.requirement_extraction import draft_university_requirements

router = APIRouter(prefix="/study-abroad", tags=["Study Abroad"])
PRIVATE_LABEL = re.compile(
    r"https?://|www\.|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?<!\d)\d{9,}(?!\d)",
    re.IGNORECASE,
)


class RefreshProgramEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: Literal["universities", "admissions", "language", "costs", "transfer"] = "admissions"
    confirm_share_program: bool = False


def public_label(value: str, limit: int) -> str:
    cleaned = " ".join(value.split()).strip()
    if not cleaned or PRIVATE_LABEL.search(cleaned):
        raise HTTPException(422, "Program labels cannot contain links or private identifiers")
    return cleaned[:limit]


@router.post(
    "/cases/{case_id}/universities/{university_id}/refresh-evidence",
    dependencies=[Depends(limit_rag_request)],
)
def refresh_program_evidence(
    case_id: str, university_id: str, body: RefreshProgramEvidence,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Live external university-host search. Do not include documents or URL tokens."""
    case = owned_case(db, str(user.id), case_id)
    school = db.scalar(select(StudyUniversity).where(
        StudyUniversity.id == university_id, StudyUniversity.case_id == case.id,
    ))
    if school is None:
        raise HTTPException(404, "Program is not in your shortlist")
    if not body.confirm_share_program:
        raise HTTPException(422, "Consent to external university program research is required")
    if safe_public_url(school.program_url) is None:
        raise HTTPException(422, "Saved program link must use public HTTPS")
    host = (urlsplit(school.program_url).hostname or "").lower().rstrip(".")
    school_label = public_label(school.name, 110)
    program = public_label(school.program, 110)
    destination = public_label(case.destination_country, 50)
    intake = public_label(case.intake, 35)
    question = (
        f"{school_label} {program}, {destination}, intake {intake}. "
        f"Find published {body.topic} requirements on this school's own website. "
        "Report explicit current criteria or say unknown. "
        "Cite evidence [W#]. Do not predict eligibility or credit transfer."
    )[:600]
    try:
        found = research_web(
            question, max_sources=4, mode="deep", include_domains=[host],
        )
        matching = [
            source for source in found.sources
            if safe_public_url(source.url) is not None
            and matching_source_host(school.program_url, source.url)
        ]
        if not matching:
            raise HTTPException(422, "No matching first-party university source found")
        annotated = [
            {**source.model_dump(mode="json"),
             "source_type": "shortlisted_program_domain_unverified"}
            for source in matching
        ]
        validate_study_citation_coverage(found.answer, annotated)
    except (UnsupportedStudyClaims, WebResearchEvidenceError) as exc:
        raise HTTPException(422, "Evidence citations are missing or untraceable") from exc
    except WebResearchUnavailable as exc:
        raise HTTPException(503, "Live university research provider is unavailable") from exc
    except LLMError as exc:
        raise HTTPException(502, "University research model could not verify evidence") from exc
    report = StudyResearchReport(
        case_id=case.id, topic=body.topic, question=question,
        answer=found.answer, sources=annotated,
        searched_at=found.searched_at.astimezone(timezone.utc).replace(tzinfo=None),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {
        "report": StudyResearchResponse.model_validate(report).model_dump(mode="json"),
        "suggestions": draft_university_requirements(
            university=school, reports=[report],
        ),
        "verification_status": "university_domain_evidence_needs_manual_review",
        "disclaimer": (
            "A cited source on the saved university hostname was found. "
            "The precise degree, intake, publication date and criteria still "
            "require applicant review. Nothing was automatically accepted."
        ),
    }
