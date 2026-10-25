"""Owner-scoped student planning. Never submits university or visa applications."""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.config.settings import settings
from app.core.datetime_utils import utc_now_naive
from app.core.rate_limit import limit_rag_request
from app.database.connection import get_db
from app.llms.types import LLMError
from app.llms import LLMProviderRequestError, LLMProviderResponseError, LLMValidationError
from app.embeddings import EmbeddingError
from app.retrieval import RetrievalProviderError, RetrievalValidationError
from app.rag import CitationValidationError, GroundedAnswerError
from app.services.rag_answer_service import answer_question
from app.models.document import Document
from app.models.study_case import StudyCase, StudyCaseDocument, StudyResearchReport, StudyUniversity
from app.models.user import User
from app.schemas.study_abroad import (
    StudyCaseCreate, StudyCaseUpdate, StudyCaseResponse, StudyChecklistUpdate,
    StudyDocumentLink, StudyDocumentResponse, StudyResearchCreate, StudyResearchResponse,
    UniversityCreate, UniversityStatusUpdate, UniversityResponse,
    StudyDocumentQuestion, StudyDocumentCitation, StudyDocumentAnswer,
)
from app.services.web_research_service import (
    WebResearchEvidenceError, WebResearchUnavailable, research_web, safe_public_url,
)
from app.study_abroad.workflows import WORKFLOWS, TOPICS, CHECKS, research_question, initial_checklist

router = APIRouter(prefix="/study-abroad", tags=["Study Abroad"])

def owned_case(db: Session, user_id: str, case_id: str) -> StudyCase:
    found = db.scalar(select(StudyCase).where(
        StudyCase.id == case_id, StudyCase.user_id == user_id))
    if found is None:
        raise HTTPException(404, "Study case not found")
    return found

@router.get("/workflows")
def list_visa_workflows() -> list[dict]:
    return [
        {"id": entry.key, "title": entry.title, "enabled": entry.enabled,
         "stages": list(entry.stages)} for entry in WORKFLOWS.values()
    ]

@router.get("/cases", response_model=list[StudyCaseResponse])
def list_study_cases(user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)) -> list[StudyCase]:
    return list(db.scalars(select(StudyCase).where(
        StudyCase.user_id == str(user.id)
    ).order_by(StudyCase.updated_at.desc()).limit(50)).all())

@router.post("/cases", response_model=StudyCaseResponse,
             status_code=status.HTTP_201_CREATED)
def create_study_case(body: StudyCaseCreate, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)) -> StudyCase:
    # All countries permitted as text; no unverified eligibility assertion.
    case = StudyCase(user_id=str(user.id), workflow=body.workflow,
        nationality=body.nationality, residence_country=body.residence_country,
        destination_country=body.destination_country, degree_level=body.degree_level,
        study_field=body.study_field, intake=body.intake, stage="profile",
        notes="", checklist=initial_checklist())
    db.add(case)
    db.commit()
    db.refresh(case)
    return case

@router.get("/cases/{case_id}", response_model=StudyCaseResponse)
def get_study_case(case_id: str, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> StudyCase:
    return owned_case(db, str(user.id), case_id)

@router.patch("/cases/{case_id}", response_model=StudyCaseResponse)
def update_study_case(case_id: str, body: StudyCaseUpdate,
                      user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)) -> StudyCase:
    case = owned_case(db, str(user.id), case_id)
    if not body.model_fields_set:
        raise HTTPException(422, "No changes provided")
    if body.stage is not None:
        case.stage = body.stage
    if body.notes is not None:
        case.notes = body.notes
    case.updated_at = utc_now_naive()
    db.commit()
    db.refresh(case)
    return case

@router.delete("/cases/{case_id}", status_code=204)
def delete_study_case(case_id: str, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)) -> Response:
    case = owned_case(db, str(user.id), case_id)
    # The case and linked snapshots are deleted; user-owned source documents remain.
    db.delete(case)
    db.commit()
    return Response(status_code=204)

@router.patch("/cases/{case_id}/checklist/{key}", response_model=StudyCaseResponse)
def update_checklist(case_id: str, key: str, body: StudyChecklistUpdate,
                     user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)) -> StudyCase:
    case = owned_case(db, str(user.id), case_id)
    if key not in dict(CHECKS):
        raise HTTPException(404, "Checklist item not found")
    if body.evidence_url is not None and safe_public_url(body.evidence_url) is None:
        raise HTTPException(422, "Only a public HTTPS source URL can be recorded")
    checklist = dict(case.checklist)
    item = dict(checklist[key])
    item["state"] = body.state
    if "evidence_url" in body.model_fields_set:
        item["evidence_url"] = body.evidence_url
    checklist[key] = item
    case.checklist = checklist
    case.updated_at = utc_now_naive()
    db.commit()
    db.refresh(case)
    return case

@router.get("/cases/{case_id}/documents", response_model=list[StudyDocumentResponse])
def list_study_documents(case_id: str, user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)) -> list[StudyDocumentResponse]:
    owned_case(db, str(user.id), case_id)
    rows = db.execute(select(StudyCaseDocument, Document).join(
        Document, StudyCaseDocument.document_id == Document.id).where(
        StudyCaseDocument.case_id == case_id, Document.user_id == str(user.id))).all()
    return [StudyDocumentResponse(document_id=doc.id,
        filename=doc.original_filename, status=doc.status,
        checklist_key=link.checklist_key) for link,doc in rows]

@router.post("/cases/{case_id}/documents", response_model=StudyDocumentResponse,
             status_code=201)
def attach_study_document(case_id: str, body: StudyDocumentLink,
                           user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)) -> StudyDocumentResponse:
    case = owned_case(db, str(user.id), case_id)
    if body.checklist_key not in dict(CHECKS):
        raise HTTPException(422, "Unknown checklist item")
    doc = db.scalar(select(Document).where(
        Document.id == body.document_id, Document.user_id == str(user.id)))
    if doc is None:
        raise HTTPException(404, "Document not found")
    if doc.status != "ready":
        raise HTTPException(409, "Process the file before attaching it")
    link = db.get(StudyCaseDocument, (case.id, doc.id))
    if link is None:
        link = StudyCaseDocument(case_id=case.id, document_id=doc.id,
                                 checklist_key=body.checklist_key)
        db.add(link)
    else:
        link.checklist_key = body.checklist_key
    checklist = dict(case.checklist)
    item = dict(checklist[body.checklist_key])
    item["state"] = "uploaded"
    item["document_id"] = doc.id
    checklist[body.checklist_key] = item
    case.checklist = checklist
    case.updated_at = utc_now_naive()
    db.commit()
    return StudyDocumentResponse(document_id=doc.id,
        filename=doc.original_filename, status=doc.status,
        checklist_key=link.checklist_key)

@router.delete("/cases/{case_id}/documents/{document_id}", status_code=204)
def unlink_study_document(case_id: str, document_id: str,
                          user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)) -> Response:
    case = owned_case(db, str(user.id), case_id)
    link = db.get(StudyCaseDocument, (case.id, document_id))
    if link is None:
        raise HTTPException(404, "Document association not found")
    db.delete(link)
    checklist = dict(case.checklist)
    item = dict(checklist[link.checklist_key])
    if item.get("document_id") == document_id:
        remaining = db.scalar(select(StudyCaseDocument.document_id).where(
            StudyCaseDocument.case_id == case.id,
            StudyCaseDocument.document_id != document_id,
            StudyCaseDocument.checklist_key == link.checklist_key,
        ))
        item["document_id"] = remaining
        item["state"] = "uploaded" if remaining is not None else "needs_verification"
    checklist[link.checklist_key] = item
    case.checklist = checklist
    case.updated_at = utc_now_naive()
    db.commit()
    return Response(status_code=204)

@router.get("/cases/{case_id}/research", response_model=list[StudyResearchResponse])
def list_case_research(case_id: str, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)) -> list[StudyResearchReport]:
    owned_case(db, str(user.id), case_id)
    return list(db.scalars(select(StudyResearchReport).where(
        StudyResearchReport.case_id == case_id
    ).order_by(StudyResearchReport.searched_at.desc()).limit(30)).all())

@router.post("/cases/{case_id}/research", response_model=StudyResearchResponse,
             dependencies=[Depends(limit_rag_request)])
def research_study_topic(case_id: str, body: StudyResearchCreate,
                         user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)) -> StudyResearchReport:
    case = owned_case(db, str(user.id), case_id)
    if not body.confirm_share_profile:
        raise HTTPException(422, "Confirm sharing limited study profile fields with the research provider")
    # Never send source document contents, passport numbers, or private attachments
    # to public search. The question only uses selected non-sensitive profile fields.
    question = research_question(body.topic, case)
    try:
        researched = research_web(question, max_sources=4, mode="deep")
    except WebResearchUnavailable as exc:
        raise HTTPException(503, "Live source research is not configured") from exc
    except WebResearchEvidenceError as exc:
        raise HTTPException(422, str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(502, "Research generation failed") from exc
    # Research results are evidence snapshots, NEVER verified legal decisions.
    report = StudyResearchReport(case_id=case.id, topic=body.topic,
        question=question, answer=researched.answer,
        sources=[source.model_dump(mode="json") for source in researched.sources],
        searched_at=researched.searched_at.replace(tzinfo=None))
    db.add(report)
    db.commit()
    db.refresh(report)
    return report

@router.get("/cases/{case_id}/universities", response_model=list[UniversityResponse])
def list_university_shortlist(case_id: str, user: User = Depends(get_current_user),
                              db: Session = Depends(get_db)) -> list[StudyUniversity]:
    owned_case(db, str(user.id), case_id)
    return list(db.scalars(select(StudyUniversity).where(
        StudyUniversity.case_id == case_id
    ).order_by(StudyUniversity.created_at.desc()).limit(40)).all())


@router.post("/cases/{case_id}/universities", response_model=UniversityResponse, status_code=201)
def add_university(case_id: str, body: UniversityCreate,
                   user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> StudyUniversity:
    owned_case(db, str(user.id), case_id)
    if safe_public_url(body.program_url) is None:
        raise HTTPException(422, "Program URL must be public HTTPS")
    shortlist = StudyUniversity(case_id=case_id, name=body.name.strip(),
        program=body.program.strip(), program_url=body.program_url,
        deadline=body.deadline.strip(), notes=body.notes.strip(),
        application_status="researching")
    db.add(shortlist)
    db.commit()
    db.refresh(shortlist)
    return shortlist


@router.patch("/cases/{case_id}/universities/{university_id}",
              response_model=UniversityResponse)
def update_university_status(case_id: str, university_id: str,
                             body: UniversityStatusUpdate,
                             user: User = Depends(get_current_user),
                             db: Session = Depends(get_db)) -> StudyUniversity:
    owned_case(db, str(user.id), case_id)
    item = db.scalar(select(StudyUniversity).where(
        StudyUniversity.id == university_id, StudyUniversity.case_id == case_id))
    if item is None:
        raise HTTPException(404, "University not in your shortlist")
    item.application_status = body.application_status
    db.commit()
    db.refresh(item)
    return item


@router.delete("/cases/{case_id}/universities/{university_id}", status_code=204)
def remove_university(case_id: str, university_id: str,
                      user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)) -> Response:
    owned_case(db, str(user.id), case_id)
    item = db.scalar(select(StudyUniversity).where(
        StudyUniversity.id == university_id, StudyUniversity.case_id == case_id))
    if item is None:
        raise HTTPException(404, "University not in your shortlist")
    db.delete(item)
    db.commit()
    return Response(status_code=204)

@router.post("/cases/{case_id}/ask-documents", response_model=StudyDocumentAnswer,
             dependencies=[Depends(limit_rag_request)])
def ask_study_documents(
    case_id: str, body: StudyDocumentQuestion,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> StudyDocumentAnswer:
    """RAG retrieval is bounded to the authenticated case's linked documents."""
    owned_case(db, str(user.id), case_id)
    if not body.confirm_share_documents:
        raise HTTPException(422, "Confirm sharing selected document excerpts with the configured AI provider")
    ids = tuple(db.scalars(
        select(StudyCaseDocument.document_id)
        .join(Document, Document.id == StudyCaseDocument.document_id)
        .where(StudyCaseDocument.case_id == case_id,
               Document.user_id == str(user.id), Document.status == "ready")
        .order_by(StudyCaseDocument.document_id)
        .limit(30)
    ).all())
    # In generic RAG, document_ids=() means ALL user files: never pass empty.
    if not ids:
        raise HTTPException(409, "Attach at least one processed document to this case")
    try:
        result = answer_question(
            db=db, user_id=str(user.id), question=body.question,
            document_ids=ids, top_k=8, max_sources=6,
            max_context_tokens=2400, max_source_tokens=600,
        )
    except RetrievalValidationError as exc:
        raise HTTPException(422, "Invalid document retrieval request") from exc
    except (RetrievalProviderError, LLMValidationError, EmbeddingError,
            LLMProviderRequestError) as exc:
        raise HTTPException(503, "Document AI provider is unavailable") from exc
    except (LLMProviderResponseError, CitationValidationError,
            GroundedAnswerError) as exc:
        raise HTTPException(502, "Answer could not be grounded in attached documents") from exc
    if any(source.document_id not in ids for source in result.citations):
        raise HTTPException(502, "Answer cited a document outside this student case")
    return StudyDocumentAnswer(
        question=result.question,
        answer=result.answer_text,
        is_refusal=result.is_refusal,
        searched_document_count=len(ids),
        citations=[
            StudyDocumentCitation(
                source_id=source.source_id,
                document_id=source.document_id,
                filename=source.original_filename,
                source_label=source.source_label,
                excerpt=source.content[:1800],
            ) for source in result.citations
        ],
    )
