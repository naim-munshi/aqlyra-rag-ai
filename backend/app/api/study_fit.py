"""Owned study-program fit APIs; never submit university applications."""
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.study_abroad import owned_case
from app.core.datetime_utils import utc_now_naive
from app.database.connection import get_db
from app.models.study_case import StudyUniversity, StudyResearchReport
from app.models.user import User
from app.schemas.study_abroad import (
    StudyApplicantFacts, ProgramRequirements, StudyProgramMatches,
    UniversityResponse,
)
from app.services.web_research_service import safe_public_url
from app.study_abroad.program_matcher import compare_programs, matching_source_host
from app.study_abroad.requirement_extraction import draft_university_requirements

router = APIRouter(prefix="/study-abroad", tags=["Study Abroad"])


@router.patch("/cases/{case_id}/applicant-facts", response_model=StudyApplicantFacts)
def save_applicant_facts(
    case_id: str, body: StudyApplicantFacts,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> StudyApplicantFacts:
    case = owned_case(db, str(user.id), case_id)
    case.applicant_facts = body.model_dump(exclude_none=True)
    case.updated_at = utc_now_naive()
    db.commit()
    return body


@router.get("/cases/{case_id}/matches", response_model=StudyProgramMatches)
def get_program_matches(
    case_id: str, user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StudyProgramMatches:
    case = owned_case(db, str(user.id), case_id)
    schools = list(db.scalars(
        select(StudyUniversity).where(StudyUniversity.case_id == case.id)
        .order_by(StudyUniversity.created_at.desc()).limit(40)
    ).all())
    reports = list(db.scalars(
        select(StudyResearchReport).where(StudyResearchReport.case_id == case.id)
        .order_by(StudyResearchReport.searched_at.desc()).limit(50)
    ).all())
    return StudyProgramMatches.model_validate(compare_programs(
        case=case, universities=schools, reports=reports,
    ))


@router.patch(
    "/cases/{case_id}/universities/{university_id}/requirements",
    response_model=UniversityResponse,
)
def save_program_requirements(
    case_id: str, university_id: str, body: ProgramRequirements,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> StudyUniversity:
    owned_case(db, str(user.id), case_id)
    school = db.scalar(select(StudyUniversity).where(
        StudyUniversity.id == university_id,
        StudyUniversity.case_id == case_id,
    ))
    if school is None:
        raise HTTPException(404, "University not in your study case")
    if body.evidence_report_id:
        report = db.scalar(select(StudyResearchReport).where(
            StudyResearchReport.id == body.evidence_report_id,
            StudyResearchReport.case_id == case_id,
            StudyResearchReport.topic.in_((
                "universities", "admissions", "language", "costs", "transfer",
            )),
        ))
        if report is None:
            raise HTTPException(422, "Research report does not belong to your study case")
        src = next((
            item for item in report.sources
            if isinstance(item, dict)
            and item.get("citation") == body.evidence_citation
        ), None)
        if src is None or not isinstance(src.get("url"), str):
            raise HTTPException(422, "Citation must be an existing saved source")
        if safe_public_url(src["url"]) is None:
            raise HTTPException(422, "Invalid public HTTPS evidence source")
        if not matching_source_host(school.program_url, src["url"]):
            raise HTTPException(422, "Evidence host must match the shortlisted university")
    school.requirements = body.model_dump(exclude_none=True)
    db.commit()
    db.refresh(school)
    return school


@router.get("/cases/{case_id}/program-candidates")
def get_program_candidates(
    case_id: str, user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Return real source links; never invent a school from search titles."""
    owned_case(db, str(user.id), case_id)
    reports = list(db.scalars(
        select(StudyResearchReport).where(
            StudyResearchReport.case_id == case_id,
            StudyResearchReport.topic.in_((
                "universities", "admissions", "transfer",
            )),
        ).order_by(StudyResearchReport.searched_at.desc()).limit(15)
    ).all())
    seen: set[str] = set()
    results: list[dict] = []
    for report in reports:
        for source in report.sources if isinstance(report.sources, list) else []:
            if not isinstance(source, dict):
                continue
            original = source.get("url")
            if not isinstance(original, str) or safe_public_url(original) is None:
                continue
            parsed = urlsplit(original)
            safe_url = urlunsplit(("https", parsed.netloc, parsed.path, "", ""))
            if safe_url in seen:
                continue
            seen.add(safe_url)
            results.append({
                "title": str(source.get("title") or "Research source")[:160],
                "url": safe_url,
                "research_report_id": report.id,
                "citation": str(source.get("citation") or "")[:12],
                "searched_at": report.searched_at.isoformat(),
                "status": "research_link_only_not_verified_program",
            })
            if len(results) >= 12:
                return results
    return results



@router.get("/cases/{case_id}/universities/{university_id}/requirement-suggestions")
def requirement_suggestions(
    case_id: str, university_id: str,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> list[dict]:
    """Derive first-party excerpt-based drafts; never update requirement facts."""
    owned_case(db, str(user.id), case_id)
    school = db.scalar(select(StudyUniversity).where(
        StudyUniversity.id == university_id,
        StudyUniversity.case_id == case_id,
    ))
    if school is None:
        raise HTTPException(404, "Program is not in your shortlist")
    reports = list(db.scalars(select(StudyResearchReport).where(
        StudyResearchReport.case_id == case_id,
        StudyResearchReport.topic.in_(
            ("universities", "admissions", "language", "costs", "transfer"),
        ),
    ).order_by(StudyResearchReport.searched_at.desc()).limit(30)).all())
    return draft_university_requirements(university=school, reports=reports)
